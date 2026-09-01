from django.conf import settings
from django.contrib.auth import login, logout
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from access.seeds import seed_access_control
from accounts.models import LoginEvent, User
from accounts.registration import RegistrationDraft
from accounts.services import LockoutService, PasswordResetService, SessionService, VerificationService
from audit.services import AuditService
from core.ip import client_ip
from merchants.services import MerchantOnboardingService
from notifications.email_service import EmailService
from portals.forms import MerchantRegisterForm, PortalLoginForm
from portals.routing import LOGIN_PATH

from .mixins import JsonView, MerchantRequiredMixin, api_error, parse_json
from .serializers import entity_type_for_registration, user_payload


def _client_ip(request):
    return client_ip(request)


def _otp_digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())[:6]


class AuthRegisterView(JsonView):
    @method_decorator(ratelimit(key="ip", rate="40/h", method="POST", block=True))
    def post(self, request):
        body = parse_json(request)
        action = body.get("action") or "details"
        draft = RegistrationDraft.load(request)

        if action == "details":
            form = MerchantRegisterForm(
                {
                    "name": body.get("fullName") or body.get("name") or "",
                    "email": body.get("email") or "",
                    "mobile": body.get("mobile") or "",
                    "address": body.get("address") or "Registered address pending",
                    "pincode": body.get("pincode") or "110001",
                    "entity_type": entity_type_for_registration(body.get("entityType") or "individual"),
                    "password": body.get("password") or "",
                    "confirm_password": body.get("password") or "",
                    "accept_terms": "on" if body.get("acceptTerms") else "",
                }
            )
            if not form.is_valid():
                errors = []
                for field, field_errors in form.errors.items():
                    for err in field_errors:
                        errors.append(f"{field}: {err}")
                return api_error(errors[0] if errors else "Invalid registration details.", fieldErrors=form.errors)
            draft.store_details(
                name=form.cleaned_data["name"],
                email=form.cleaned_data["email"],
                mobile=form.cleaned_data["mobile"],
                address=form.cleaned_data["address"],
                pincode=form.cleaned_data["pincode"],
                entity_type=form.cleaned_data["entity_type"],
                password=form.cleaned_data["password"],
            )
            email_code = draft.issue_otp_if_needed("email")
            mobile_code = draft.issue_otp_if_needed("mobile")
            draft.set_step("verify")
            draft.save(request)
            payload = {
                "step": draft.step,
                "emailVerified": bool(draft.data.get("email_verified")),
                "mobileVerified": bool(draft.data.get("mobile_verified")),
                "otpWaitEmail": draft.otp_wait_seconds("email"),
                "otpWaitMobile": draft.otp_wait_seconds("mobile"),
            }
            if settings.DEBUG:
                if email_code:
                    payload["debugEmailOtp"] = email_code
                if mobile_code:
                    payload["debugMobileOtp"] = mobile_code
            return self.ok(payload)

        if action == "send_otp":
            channel = body.get("channel")
            if channel not in {"email", "mobile"}:
                return api_error("channel must be email or mobile.")
            code = draft.issue_otp(channel)
            draft.save(request)
            payload = {"step": draft.step, "otpWait": draft.otp_wait_seconds(channel)}
            if settings.DEBUG:
                payload["debugOtp"] = code
            return self.ok(payload)

        if action == "confirm_otp":
            channel = body.get("channel")
            code = _otp_digits(body.get("code") or "")
            if channel not in {"email", "mobile"}:
                return api_error("channel must be email or mobile.")
            if len(code) != 6:
                return api_error("Enter a valid 6-digit code.")
            if not draft.confirm_otp(channel, code):
                draft.save(request)
                return api_error("The OTP is incorrect or has expired.")
            draft.save(request)
            return self.ok(
                {
                    "step": draft.step,
                    "emailVerified": bool(draft.data.get("email_verified")),
                    "mobileVerified": bool(draft.data.get("mobile_verified")),
                }
            )

        if action == "finish":
            if not body.get("acceptTerms"):
                return api_error("Accept the Terms and Conditions and Privacy Policy.")
            if not draft.can_preview() or not draft.data.get("password_hash"):
                return api_error("Complete details and verification before creating the account.")
            seed_access_control()
            now = timezone.now()
            user = User(
                email=draft.data["email"],
                name=draft.data["name"],
                mobile=draft.data["mobile"],
                user_type=User.UserType.MERCHANT,
                password=draft.data["password_hash"],
                email_verified_at=now if draft.data.get("email_verified") else None,
                mobile_verified_at=now if draft.data.get("mobile_verified") else None,
            )
            user.save()
            from access.policy import Policy

            Policy.grant_role(user, "merchant")
            application = MerchantOnboardingService.start(
                user,
                entity_type=draft.data.get("entity_type") or "INDIVIDUAL",
            )
            MerchantOnboardingService.seed_registered_address(
                application,
                address=draft.data.get("address") or "",
                pincode=draft.data.get("pincode") or "",
            )
            AuditService.record(
                actor=user,
                action="auth.register",
                resource_type="user",
                resource_id=str(user.pk),
                request=request,
            )
            EmailService.send(
                to=user.email,
                template="welcome",
                context={
                    "user": user,
                    "email": user.email,
                    "action_url": "/login/",
                    "action_label": "Sign in",
                },
                fail_silently=True,
            )
            RegistrationDraft.clear(request)
            login(request, user)
            request.session.cycle_key()
            SessionService.track(
                user,
                session_key=request.session.session_key,
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            return self.ok({"user": user_payload(user)})

        return api_error("Unknown registration action.")


class AuthLoginView(JsonView):
    @method_decorator(ratelimit(key="ip", rate="8/m", method="POST", block=True))
    def post(self, request):
        body = parse_json(request)
        email = (body.get("identifier") or body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        remaining = LockoutService.locked_seconds_remaining(email)
        if remaining:
            LoginEvent.objects.create(
                email=email,
                result=LoginEvent.Result.FAILURE,
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            )
            return api_error("Too many failed sign-in attempts. Try again later.", status=429)

        form = PortalLoginForm({"email": email, "password": password})
        if not form.is_valid():
            LockoutService.record_failure(email)
            LoginEvent.objects.create(
                email=email,
                result=LoginEvent.Result.FAILURE,
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            )
            return api_error("The email or password is incorrect.", status=400)

        user = form.cleaned_data["user"]
        if user.user_type != User.UserType.MERCHANT:
            return api_error(
                "Admin and staff must sign in through the Payswap staff portal.",
                status=403,
                use_staff_portal=True,
                staff_login_url=LOGIN_PATH,
            )

        login(request, user)
        request.session.cycle_key()
        user.last_activity_at = timezone.now()
        user.save(update_fields=["last_activity_at"])
        SessionService.track(
            user,
            session_key=request.session.session_key,
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        LoginEvent.objects.create(
            user=user,
            email=user.email,
            result=LoginEvent.Result.SUCCESS,
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        )
        AuditService.record(
            actor=user,
            action="auth.login",
            resource_type="user",
            resource_id=str(user.pk),
            request=request,
        )
        LockoutService.reset(email)
        return self.ok({"user": user_payload(user)})


class AuthMeView(MerchantRequiredMixin, JsonView):
    def get(self, request):
        return self.ok({"user": user_payload(request.user)})


class AuthLogoutView(MerchantRequiredMixin, JsonView):
    def post(self, request):
        AuditService.record(
            actor=request.user,
            action="auth.logout",
            resource_type="user",
            resource_id=str(request.user.pk),
            request=request,
        )
        logout(request)
        return self.ok({})


class AuthPasswordResetView(JsonView):
    @method_decorator(ratelimit(key="ip", rate="5/h", method="POST", block=True))
    def post(self, request):
        body = parse_json(request)
        action = body.get("action") or "request"
        if action == "request":
            email = (body.get("identifier") or body.get("email") or "").strip()
            PasswordResetService.request_reset(email=email, request=request)
            return self.ok({"sent": True})
        return api_error("Password reset via OTP is not supported. Check your email for a reset link.")


class AuthVerifyView(JsonView):
    @method_decorator(ratelimit(key="ip", rate="20/h", method="POST", block=True))
    def post(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return api_error("Authentication required.", status=401)
        if user.user_type != User.UserType.MERCHANT:
            return api_error(
                "Corporate partner access only.",
                status=403,
                use_staff_portal=True,
                staff_login_url=LOGIN_PATH,
            )

        body = parse_json(request)
        action = body.get("action") or "confirm"
        channel = body.get("channel")
        if channel not in {"email", "mobile"}:
            return api_error("channel must be email or mobile.")

        if action == "send_otp":
            try:
                issued = VerificationService.issue(user, channel=channel)
            except ValidationError as exc:
                return api_error(" ".join(exc.messages))
            payload = {"sent": True}
            if settings.DEBUG:
                payload["debugOtp"] = issued.debug_code
            return self.ok(payload)

        if action == "confirm":
            code = _otp_digits(body.get("code") or "")
            if len(code) != 6:
                return api_error("Enter a valid 6-digit code.")
            if not VerificationService.confirm(user, channel=channel, code=code):
                return api_error("The OTP is incorrect or has expired.")
            user.refresh_from_db()
            return self.ok({"user": user_payload(user)})

        return api_error("Unknown verification action.")
