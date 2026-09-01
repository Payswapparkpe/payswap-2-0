"""Session-backed merchant registration wizard (details → verify → preview)."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from merchants.models import Merchant
from notifications.email_service import EmailService
from notifications.sms_service import SmsService

SESSION_KEY = "merchant_register"
OTP_TTL_SECONDS = 300
OTP_COOLDOWN_SECONDS = 30

STEPS = ("details", "verify", "preview")
STEP_LABELS = {
    "details": "Details",
    "verify": "Verify",
    "preview": "Preview",
}


def _hash_code(code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


def _mask_email(email: str) -> str:
    local, _, domain = (email or "").partition("@")
    if not domain:
        return ""
    return f"{local[:1]}***@{domain}"


def _mask_mobile(mobile: str) -> str:
    digits = "".join(ch for ch in (mobile or "") if ch.isdigit())
    return f"******{digits[-4:]}" if len(digits) >= 4 else "***"


def _test_code_ok(code: str) -> bool:
    return bool(getattr(settings, "AUTH_TEST_MODE", False)) and code == getattr(settings, "TEST_OTP", "")


def _aware_dt(value: str):
    parsed = datetime.fromisoformat(value)
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


class RegistrationDraft:
    def __init__(self, data: dict | None = None):
        self.data = dict(data or {})
        self.data.setdefault("step", "details")

    @classmethod
    def load(cls, request) -> "RegistrationDraft":
        return cls(request.session.get(SESSION_KEY) or {})

    def save(self, request) -> None:
        request.session[SESSION_KEY] = self.data
        request.session.modified = True

    @staticmethod
    def clear(request) -> None:
        request.session.pop(SESSION_KEY, None)
        request.session.modified = True

    @property
    def step(self) -> str:
        current = self.data.get("step") or "details"
        if current == "terms":
            current = "preview"
        return current if current in STEPS else "details"

    def set_step(self, step: str) -> None:
        if step == "terms":
            step = "preview"
        if step in STEPS:
            self.data["step"] = step

    def stepper(self) -> list[dict]:
        current = self.step
        items = []
        reached = True
        for key in STEPS:
            state = "current" if key == current else ("done" if reached and key != current else "pending")
            if key == current:
                reached = False
            items.append({"key": key, "label": STEP_LABELS[key], "state": state, "url": f"?step={key}"})
        return items

    def preview(self) -> dict:
        return {
            "name": self.data.get("name") or "",
            "email": _mask_email(self.data.get("email") or ""),
            "email_full": self.data.get("email") or "",
            "mobile": _mask_mobile(self.data.get("mobile") or ""),
            "address": self.data.get("address") or "",
            "pincode": self.data.get("pincode") or "",
            "entity_type": self.data.get("entity_type") or Merchant.EntityType.INDIVIDUAL,
            "entity_type_label": dict(Merchant.EntityType.choices).get(
                self.data.get("entity_type") or Merchant.EntityType.INDIVIDUAL,
                "Individual",
            ),
            "email_verified": bool(self.data.get("email_verified")),
            "mobile_verified": bool(self.data.get("mobile_verified")),
        }

    def contacts_verified(self) -> bool:
        return bool(self.data.get("email_verified") and self.data.get("mobile_verified"))

    def can_preview(self) -> bool:
        return self.contacts_verified()

    def store_details(self, *, name, email, mobile, address, pincode, entity_type, password) -> None:
        email = email.lower().strip()
        mobile = mobile.strip()
        if self.data.get("email") != email:
            self.data["email_verified"] = False
            self.data["email_otp"] = {}
        if self.data.get("mobile") != mobile:
            self.data["mobile_verified"] = False
            self.data["mobile_otp"] = {}
        if entity_type not in Merchant.EntityType.values:
            entity_type = Merchant.EntityType.INDIVIDUAL
        self.data.update(
            {
                "name": name.strip(),
                "email": email,
                "mobile": mobile,
                "address": (address or "").strip(),
                "pincode": (pincode or "").strip(),
                "entity_type": entity_type,
                "password_hash": make_password(password),
            }
        )

    def _otp_bucket(self, channel: str) -> dict:
        return dict(self.data.get(f"{channel}_otp") or {})

    def otp_wait_seconds(self, channel: str) -> int:
        if self.data.get(f"{channel}_verified"):
            return 0
        sent_at = self._otp_bucket(channel).get("sent_at")
        if not sent_at:
            return 0
        elapsed = (timezone.now() - _aware_dt(sent_at)).total_seconds()
        return max(0, OTP_COOLDOWN_SECONDS - int(elapsed))

    def issue_otp_if_needed(self, channel: str) -> str | None:
        if self.data.get(f"{channel}_verified") or self.otp_wait_seconds(channel):
            return None
        return self.issue_otp(channel)

    def issue_otp(self, channel: str) -> str:
        destination = self.data.get("email") if channel == "email" else self.data.get("mobile")
        if not destination:
            raise ValidationError("Save your details before requesting a verification code.")
        wait = self.otp_wait_seconds(channel)
        if wait:
            raise ValidationError(f"A code was already sent. Wait {wait} seconds.")
        now = timezone.now()
        code = f"{secrets.randbelow(1_000_000):06d}"
        self.data[f"{channel}_otp"] = {
            "hash": _hash_code(code),
            "expires_at": (now + timedelta(seconds=OTP_TTL_SECONDS)).isoformat(),
            "attempts": 0,
            "sent_at": now.isoformat(),
        }
        if channel == "email":
            EmailService.send(
                to=destination,
                template="verification_code",
                context={"code": code, "action_url": "/merchant/register/?step=verify", "email": destination},
                sensitive=True,
            )
        else:
            SmsService.send(
                to=destination,
                template="verification_code",
                context={"code": code},
                fail_silently=True,
                sensitive=True,
            )
        return code

    def confirm_otp(self, channel: str, code: str) -> bool:
        destination = self.data.get("email") if channel == "email" else self.data.get("mobile")
        if _test_code_ok(code) and destination:
            self.data[f"{channel}_verified"] = True
            self.data[f"{channel}_otp"] = {}
            return True
        bucket = self._otp_bucket(channel)
        if not bucket:
            return False
        expires = _aware_dt(bucket["expires_at"])
        if expires < timezone.now():
            return False
        attempts = int(bucket.get("attempts") or 0)
        if attempts >= 5:
            return False
        bucket["attempts"] = attempts + 1
        self.data[f"{channel}_otp"] = bucket
        if not _test_code_ok(code) and not hmac.compare_digest(bucket.get("hash", ""), _hash_code(code)):
            return False
        self.data[f"{channel}_verified"] = True
        self.data[f"{channel}_otp"] = {}
        return True
