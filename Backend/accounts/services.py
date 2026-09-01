import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from audit.services import AuditService
from notifications.email_service import EmailService
from notifications.sms_service import SmsService

from .models import (
    PasskeyCredential,
    RecoveryCode,
    SecurityCredential,
    User,
    UserSession,
    VerificationChallenge,
)


def _hash_code(code: str) -> str:
    """Keyed HMAC-SHA256 of the OTP; plaintext codes are never stored."""
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


def _mask_destination(destination: str) -> str:
    if "@" in destination:
        local, _, domain = destination.partition("@")
        return f"{local[:1]}***@{domain}"
    digits = "".join(ch for ch in destination if ch.isdigit())
    return f"******{digits[-4:]}" if len(digits) >= 4 else "***"


def _test_code_ok(code: str) -> bool:
    """Test OTP is accepted only when AUTH_TEST_MODE is on.

    core/settings.py fails startup when AUTH_TEST_MODE is enabled in a
    production environment, so this branch is unreachable in production.
    """
    return bool(getattr(settings, "AUTH_TEST_MODE", False)) and code == getattr(settings, "TEST_OTP", "")


@dataclass
class IssuedChallenge:
    challenge: VerificationChallenge
    debug_code: str


class VerificationService:
    @staticmethod
    def issue(user, *, channel: str, purpose: str = "verification") -> IssuedChallenge:
        now = timezone.now()
        cooldown = getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 30)
        recent = (
            VerificationChallenge.objects.filter(
                user=user, channel=channel, purpose=purpose, consumed_at__isnull=True
            )
            .order_by("-created_at")
            .first()
        )
        if recent and (now - recent.created_at).total_seconds() < cooldown:
            wait = cooldown - int((now - recent.created_at).total_seconds())
            raise ValidationError(f"A code was already sent. Wait {wait} seconds.")
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires = now + timedelta(seconds=getattr(settings, "OTP_EXPIRY_SECONDS", 300))
        VerificationChallenge.objects.filter(
            user=user, channel=channel, purpose=purpose, consumed_at__isnull=True
        ).update(consumed_at=now)
        destination = user.email if channel == "email" else user.mobile
        challenge = VerificationChallenge.objects.create(
            user=user,
            channel=channel,
            purpose=purpose,
            destination_masked=_mask_destination(destination or ""),
            code_hash=_hash_code(code),
            expires_at=expires,
            max_attempts=getattr(settings, "OTP_MAX_ATTEMPTS", 5),
            request_id=secrets.token_hex(8),
        )
        if channel == "email":
            EmailService.send(
                to=user.email,
                template="verification_code",
                context={"user": user, "code": code, "action_url": "/merchant/verify/email/"},
                sensitive=True,
            )
        elif channel == "mobile" and user.mobile:
            SmsService.send(
                to=user.mobile,
                template="verification_code",
                context={"user": user, "code": code},
                fail_silently=True,
                sensitive=True,
            )
        AuditService.record(
            actor=user,
            action="otp.sent",
            resource_type="user",
            resource_id=str(user.pk),
            after={"channel": channel, "purpose": purpose, "destination": challenge.destination_masked},
            request=None,
        )
        return IssuedChallenge(challenge=challenge, debug_code=code)

    @staticmethod
    def confirm(user, *, channel: str, code: str, purpose: str = "verification") -> bool:
        if _test_code_ok(code):
            if purpose == VerificationChallenge.Purpose.VERIFICATION:
                now = timezone.now()
                if channel == "email":
                    user.email_verified_at = now
                    user.save(update_fields=["email_verified_at"])
                elif channel == "mobile":
                    user.mobile_verified_at = now
                    user.save(update_fields=["mobile_verified_at"])
            return True
        challenge = (
            VerificationChallenge.objects.filter(user=user, channel=channel, purpose=purpose)
            .order_by("-created_at")
            .first()
        )
        if challenge is None or challenge.expires_at < timezone.now():
            return False
        if challenge.consumed_at:
            raise ValidationError("This verification code has already been used.")
        if challenge.attempts >= (challenge.max_attempts or 5):
            return False
        challenge.attempts += 1
        if not _test_code_ok(code) and not hmac.compare_digest(challenge.code_hash, _hash_code(code)):
            challenge.save(update_fields=["attempts"])
            AuditService.record(
                actor=user,
                action="otp.failed",
                resource_type="user",
                resource_id=str(user.pk),
                result="failure",
                after={"channel": channel, "purpose": purpose},
            )
            return False
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=["attempts", "consumed_at"])
        AuditService.record(
            actor=user,
            action="otp.verified",
            resource_type="user",
            resource_id=str(user.pk),
            after={"channel": channel, "purpose": purpose},
        )
        if purpose != VerificationChallenge.Purpose.VERIFICATION:
            return True
        now = timezone.now()
        if channel == "email":
            user.email_verified_at = now
            user.save(update_fields=["email_verified_at"])
        elif channel == "mobile":
            user.mobile_verified_at = now
            user.save(update_fields=["mobile_verified_at"])
        return True


MPIN_FAILURE_THRESHOLD = 5
MPIN_LOCK_MINUTES = 15

_mpin_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


class MpinService:
    """MPIN credential: Argon2id-hashed, locked after repeated failures."""

    @staticmethod
    def _validate(mpin: str) -> str:
        value = (mpin or "").strip()
        if not re.fullmatch(r"\d{4,6}", value):
            raise ValidationError("MPIN must be 4 to 6 digits.")
        return value

    @staticmethod
    def _credential(user) -> SecurityCredential:
        credential, _ = SecurityCredential.objects.get_or_create(user=user)
        return credential

    @classmethod
    def set(cls, user, mpin: str, *, request=None) -> SecurityCredential:
        value = cls._validate(mpin)
        credential = cls._credential(user)
        now = timezone.now()
        created = not credential.mpin_hash
        credential.mpin_hash = _mpin_hasher.hash(value)
        credential.mpin_enabled = True
        if created:
            credential.mpin_created_at = now
        credential.mpin_changed_at = now
        credential.mpin_failed_attempts = 0
        credential.mpin_locked_until = None
        credential.save()
        AuditService.record(
            actor=user,
            action="mpin.created" if created else "mpin.changed",
            resource_type="user",
            resource_id=str(user.pk),
            request=request,
        )
        if not created:
            EmailService.send(
                to=user.email,
                template="generic_notice",
                context={
                    "user": user,
                    "title": "Your MPIN was changed",
                    "body": "Your PayswapHub MPIN was changed. If this was not you, reset it immediately and contact support.",
                },
                fail_silently=True,
            )
        return credential

    @classmethod
    def verify(cls, user, mpin: str, *, request=None) -> bool:
        credential = SecurityCredential.objects.filter(user=user, mpin_enabled=True).first()
        if credential is None or not credential.mpin_hash:
            return False
        now = timezone.now()
        if credential.mpin_locked_until and credential.mpin_locked_until > now:
            raise ValidationError(
                f"Too many incorrect attempts. Try again after {credential.mpin_locked_until:%H:%M}."
            )
        try:
            ok = _mpin_hasher.verify(credential.mpin_hash, (mpin or "").strip())
        except (VerificationError, InvalidHash):
            ok = False
        if ok:
            if _mpin_hasher.check_needs_rehash(credential.mpin_hash):
                credential.mpin_hash = _mpin_hasher.hash((mpin or "").strip())
            credential.mpin_failed_attempts = 0
            credential.mpin_locked_until = None
            credential.save()
            return True
        credential.mpin_failed_attempts += 1
        if credential.mpin_failed_attempts >= MPIN_FAILURE_THRESHOLD:
            credential.mpin_locked_until = now + timedelta(minutes=MPIN_LOCK_MINUTES)
            credential.mpin_failed_attempts = 0
        credential.save()
        AuditService.record(
            actor=user,
            action="mpin.failed",
            resource_type="user",
            resource_id=str(user.pk),
            result="failure",
            request=request,
        )
        return False

    @classmethod
    def change(cls, user, current: str, new: str, *, request=None) -> None:
        if not cls.verify(user, current, request=request):
            raise ValidationError("The current MPIN is incorrect.")
        cls.set(user, new, request=request)


class MfaService:
    @staticmethod
    def enrol(user):
        TOTPDevice.objects.filter(user=user, name="authenticator").delete()
        device = TOTPDevice.objects.create(user=user, name="authenticator", confirmed=False)
        return device, device.key

    @staticmethod
    def current_token(secret_or_device) -> str:
        if isinstance(secret_or_device, TOTPDevice):
            device = secret_or_device
        elif isinstance(secret_or_device, str) and len(secret_or_device) > 8:
            device = TOTPDevice.objects.filter(key=secret_or_device).first()
            if device is None:
                from binascii import unhexlify

                totp = TOTP(unhexlify(secret_or_device.encode()))
                return f"{totp.token():06d}"
        else:
            raise ValidationError("Authenticator setup is incomplete.")
        totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
        return f"{totp.token():06d}"

    @staticmethod
    def verify(user, token: str) -> bool:
        device = TOTPDevice.objects.filter(user=user, name="authenticator").first()
        if device is None:
            return False
        ok = device.verify_token(token)
        if ok and not device.confirmed:
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            user.mfa_enforced = True
            user.save(update_fields=["mfa_enforced"])
        return ok

    @staticmethod
    def generate_recovery_codes(user, *, count: int = 8) -> list[str]:
        """Rotate single-use recovery codes. Plaintext is returned exactly once."""
        codes = [f"{secrets.randbelow(10**8):08d}" for _ in range(count)]
        now = timezone.now()
        RecoveryCode.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
        RecoveryCode.objects.bulk_create(
            RecoveryCode(user=user, code_hash=_hash_code(code)) for code in codes
        )
        AuditService.record(
            actor=user,
            action="totp.recovery_codes_generated",
            resource_type="user",
            resource_id=str(user.pk),
        )
        return codes

    @staticmethod
    def verify_recovery_code(user, code: str) -> bool:
        record = RecoveryCode.objects.filter(
            user=user, code_hash=_hash_code((code or "").strip()), used_at__isnull=True
        ).first()
        if record is None:
            return False
        record.used_at = timezone.now()
        record.save(update_fields=["used_at"])
        AuditService.record(
            actor=user,
            action="totp.recovery_code_used",
            resource_type="user",
            resource_id=str(user.pk),
        )
        return True


class StepUpService:
    SESSION_KEY = "_step_up_at"
    TTL_SECONDS = 5 * 60

    @staticmethod
    def mark(session) -> None:
        session[StepUpService.SESSION_KEY] = timezone.now().timestamp()

    @staticmethod
    def is_satisfied(user, session) -> bool:
        stamped = session.get(StepUpService.SESSION_KEY)
        if not stamped:
            return False
        return (timezone.now().timestamp() - float(stamped)) < StepUpService.TTL_SECONDS

    @staticmethod
    def require(user, session) -> None:
        if not StepUpService.is_satisfied(user, session):
            raise ValidationError("Step-up authentication is required for this action.")


class SessionService:
    @staticmethod
    def track(user, *, session_key, ip_address=None, user_agent="") -> UserSession:
        return UserSession.objects.create(
            user=user,
            session_key=session_key or "",
            ip_address=ip_address,
            user_agent=(user_agent or "")[:255],
        )

    @staticmethod
    def revoke(tracked: UserSession, *, actor, request=None) -> UserSession:
        from django.contrib.sessions.models import Session

        tracked.revoked_at = timezone.now()
        tracked.save(update_fields=["revoked_at"])
        if tracked.session_key:
            Session.objects.filter(session_key=tracked.session_key).delete()
        prefix = {
            tracked.user.UserType.ADMIN: "/administration",
            tracked.user.UserType.EMPLOYEE: "/employee",
            tracked.user.UserType.MERCHANT: "/merchant",
        }.get(tracked.user.user_type, "/merchant")
        EmailService.send(
            to=tracked.user.email,
            template="session_revoked",
            context={"user": tracked.user, "action_url": f"{prefix}/sessions/"},
            fail_silently=True,
        )
        AuditService.record(
            actor=actor,
            action="session.revoke",
            resource_type="user",
            resource_id=str(tracked.user_id),
            request=request,
        )
        return tracked

    @staticmethod
    def revoke_all(user, *, actor, request=None) -> int:
        tracked = list(UserSession.objects.filter(user=user, revoked_at__isnull=True))
        keys = [item.session_key for item in tracked if item.session_key]
        if keys:
            Session.objects.filter(session_key__in=keys).delete()
        now = timezone.now()
        count = UserSession.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=now)
        prefix = {
            user.UserType.ADMIN: "/administration",
            user.UserType.EMPLOYEE: "/employee",
            user.UserType.MERCHANT: "/merchant",
        }.get(user.user_type, "/merchant")
        EmailService.send(
            to=user.email,
            template="session_revoked",
            context={"user": user, "action_url": f"{prefix}/sessions/"},
            fail_silently=True,
        )
        AuditService.record(
            actor=actor,
            action="session.revoke",
            resource_type="user",
            resource_id=str(user.pk),
            request=request,
            after={"sessions": count},
        )
        return count


class PasskeyService:
    SESSION_KEY = "passkey_challenge"

    @staticmethod
    def issue_challenge(session) -> str:
        challenge = secrets.token_urlsafe(32)
        session[PasskeyService.SESSION_KEY] = challenge
        return challenge

    @staticmethod
    def register(user, *, session, credential_id, public_key_hex, challenge) -> PasskeyCredential:
        if session.get(PasskeyService.SESSION_KEY) != challenge:
            raise ValidationError("The passkey challenge is invalid or has expired.")
        session.pop(PasskeyService.SESSION_KEY, None)
        cred, _ = PasskeyCredential.objects.update_or_create(
            credential_id=credential_id,
            defaults={"user": user, "public_key_hex": public_key_hex},
        )
        AuditService.record(
            actor=user,
            action="passkey.register",
            resource_type="user",
            resource_id=str(user.pk),
        )
        return cred

    @staticmethod
    def authenticate(user, *, session, credential_id, signature_hex, challenge) -> bool:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        if session.get(PasskeyService.SESSION_KEY) != challenge:
            return False
        cred = PasskeyCredential.objects.filter(user=user, credential_id=credential_id).first()
        if cred is None:
            return False
        try:
            public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(cred.public_key_hex))
            public.verify(bytes.fromhex(signature_hex), challenge.encode())
        except (InvalidSignature, ValueError):
            return False
        session.pop(PasskeyService.SESSION_KEY, None)
        cred.sign_count += 1
        cred.save(update_fields=["sign_count"])
        return True


class LockoutService:
    """Cache-backed account lockout keyed on login email.

    After FAILURE_THRESHOLD failed attempts inside FAILURE_WINDOW_SECONDS the
    account is locked for LOCK_SECONDS. Counters live in the shared cache
    (Redis in production), so lockouts hold across processes and restarts.
    """

    FAILURE_THRESHOLD = 5
    FAILURE_WINDOW_SECONDS = 10 * 60
    LOCK_SECONDS = 15 * 60

    @staticmethod
    def _normalise(email: str) -> str:
        return (email or "").strip().lower()

    @classmethod
    def _fail_key(cls, email: str) -> str:
        return f"auth:fail:{cls._normalise(email)}"

    @classmethod
    def _lock_key(cls, email: str) -> str:
        return f"auth:lock:{cls._normalise(email)}"

    @classmethod
    def locked_seconds_remaining(cls, email: str) -> int:
        email = cls._normalise(email)
        if not email:
            return 0
        deadline = cache.get(cls._lock_key(email))
        if not deadline:
            return 0
        remaining = int(float(deadline) - timezone.now().timestamp())
        return max(remaining, 0)

    @classmethod
    def record_failure(cls, email: str) -> None:
        email = cls._normalise(email)
        if not email:
            return
        now = timezone.now().timestamp()
        window_start = now - cls.FAILURE_WINDOW_SECONDS
        attempts = [ts for ts in cache.get(cls._fail_key(email), []) if ts > window_start]
        attempts.append(now)
        if len(attempts) >= cls.FAILURE_THRESHOLD:
            cache.set(cls._lock_key(email), now + cls.LOCK_SECONDS, timeout=cls.LOCK_SECONDS + 60)
            cache.delete(cls._fail_key(email))
        else:
            cache.set(cls._fail_key(email), attempts, timeout=cls.FAILURE_WINDOW_SECONDS + 60)

    @classmethod
    def reset(cls, email: str) -> None:
        cache.delete(cls._fail_key(email))
        cache.delete(cls._lock_key(email))


class PasswordResetService:
    """Signed-token password reset. The token embeds the password hash, so it
    self-invalidates once the password changes; sessions are revoked on use."""

    @staticmethod
    def request_reset(*, email: str, request=None) -> bool:
        """Always returns True; never reveals whether the account exists."""
        email = (email or "").strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        AuditService.record(
            actor=user,
            action="auth.password_reset.request",
            resource_type="user",
            resource_id=str(user.pk) if user else email,
            result="success" if user else "ignored",
            request=request,
        )
        if user is None:
            return True
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f"{settings.PUBLIC_BASE_URL}/password-reset/confirm/{uid}/{token}/"
        EmailService.send(
            to=user.email,
            template="password_reset",
            context={"user": user, "action_url": link, "action_label": "Choose a new password"},
            sensitive=True,
        )
        return True

    @staticmethod
    def resolve(uidb64: str, token: str):
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return None
        if not user.is_active or not default_token_generator.check_token(user, token):
            return None
        return user

    @staticmethod
    def confirm(*, uidb64: str, token: str, new_password: str, request=None) -> User:
        user = PasswordResetService.resolve(uidb64, token)
        if user is None:
            raise ValidationError("This password reset link is invalid or has expired.")
        validate_password(new_password, user=user)
        user.set_password(new_password)
        user.save(update_fields=["password"])
        SessionService.revoke_all(user, actor=user)
        LockoutService.reset(user.email)
        AuditService.record(
            actor=user,
            action="auth.password_reset.confirm",
            resource_type="user",
            resource_id=str(user.pk),
            request=request,
        )
        EmailService.send(
            to=user.email,
            template="generic_notice",
            context={
                "user": user,
                "title": "Your password was changed",
                "body": "Your PayswapHub password was changed and all existing sessions were signed out. If this was not you, contact support immediately.",
                "action_url": "/login/",
                "action_label": "Sign in",
            },
            sensitive=False,
        )
        return user
