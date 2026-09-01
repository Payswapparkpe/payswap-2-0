from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import RedirectView
from django_ratelimit.decorators import ratelimit

from access.policy import Policy
from access.seeds import seed_access_control
from accounts.models import LoginEvent, User
from accounts.registration import STEPS, RegistrationDraft
from accounts.services import LockoutService, PasswordResetService, SessionService
from audit.services import AuditService
from core.ip import client_ip
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService
from notifications.email_service import EmailService
from portals.forms import (
    MerchantRegisterForm,
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
    PortalLoginForm,
)
from portals.mixins import staff_requires_otp
from portals.routing import (
    LOGIN_PATH,
    MFA_PATH,
    MFA_SETUP_PATH,
    partner_login_url,
    portal_home,
    post_login_url,
)
from portals.views.errors import too_many_requests


def _client_ip(request):
    return client_ip(request)


def _otp_digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())[:6]


def ratelimit_denied(request, exception):
    return too_many_requests(request, exception)


class LoginRedirectView(RedirectView):
    url = LOGIN_PATH
    query_string = True
    permanent = False


class UnifiedLoginView(View):
    template_name = "portals/auth/login.html"

    @method_decorator(ratelimit(key="ip", rate="8/m", method="POST", block=True))
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(portal_home(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": PortalLoginForm(),
                "next": request.GET.get("next", ""),
                "partner_console_login_url": partner_login_url(),
            },
        )

    def post(self, request):
        form = PortalLoginForm(request.POST)
        nxt = request.POST.get("next", "")
        email = request.POST.get("email", "")
        remaining = LockoutService.locked_seconds_remaining(email)
        if remaining:
            LoginEvent.objects.create(
                email=email,
                result=LoginEvent.Result.FAILURE,
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            )
            AuditService.record(
                action="auth.login",
                result="failure",
                reason="Account temporarily locked after repeated failures.",
                resource_type="user",
                resource_id=email,
                request=request,
            )
            form.add_error(None, "Too many failed sign-in attempts. Try again later.")
            return render(request, self.template_name, {"form": form, "next": nxt}, status=429)
        if form.is_valid():
            user = form.cleaned_data["user"]
            request.session["post_login_next"] = nxt
            if user.mfa_enforced:
                request.session["pending_mfa_user"] = user.pk
                return redirect(MFA_PATH)
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
            ua = request.META.get("HTTP_USER_AGENT", "")[:255]
            prior_same_agent = LoginEvent.objects.filter(
                user=user, result=LoginEvent.Result.SUCCESS, user_agent=ua
            ).count()
            new_device = prior_same_agent <= 1
            EmailService.send_login_alert(
                user=user,
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                new_device=new_device,
            )
            if staff_requires_otp(user) and not user.mfa_enforced:
                return redirect(MFA_SETUP_PATH)
            LockoutService.reset(email)
            return redirect(post_login_url(request, user))
        LockoutService.record_failure(email)
        LoginEvent.objects.create(
            email=request.POST.get("email", ""),
            result=LoginEvent.Result.FAILURE,
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        )
        AuditService.record(
            action="auth.login",
            result="failure",
            resource_type="user",
            resource_id=request.POST.get("email", ""),
            request=request,
        )
        return render(
            request,
            self.template_name,
            {"form": form, "next": nxt},
            status=400,
        )


class PortalLogoutView(View):
    next_url = LOGIN_PATH

    def post(self, request):
        if request.user.is_authenticated:
            AuditService.record(
                actor=request.user,
                action="auth.logout",
                resource_type="user",
                resource_id=str(request.user.pk),
                request=request,
            )
        logout(request)
        return redirect(self.next_url)


class MerchantRegisterView(View):
    template_name = "portals/auth/register.html"

    @method_decorator(ratelimit(key="ip", rate="40/h", method="POST", block=True))
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(portal_home(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        draft = RegistrationDraft.load(request)
        requested = request.GET.get("step")
        if requested == "terms":
            requested = "preview"
        if requested in STEPS:
            if requested in {"verify", "preview"} and not draft.data.get("email"):
                draft.set_step("details")
            elif requested == "preview" and not draft.can_preview():
                draft.set_step("verify")
            else:
                draft.set_step(requested)
            draft.save(request)
        return self._render(request, draft, MerchantRegisterForm(initial=self._initial(draft)))

    def post(self, request):
        draft = RegistrationDraft.load(request)
        action = request.POST.get("action") or "continue"
        step = request.POST.get("step") or draft.step
        # Legacy single-post without terms still fails closed (legal acceptance).
        if (
            action == "continue"
            and not request.POST.get("step")
            and request.POST.get("password")
            and request.POST.get("accept_terms") != "on"
            and step in {"details", "preview", "terms"}
            and not draft.data.get("email")
        ):
            form = MerchantRegisterForm(request.POST)
            form.is_valid()
            form.add_error(
                "accept_terms",
                "Accept the Terms and Conditions and Privacy Policy.",
            )
            draft.set_step("details")
            return self._render(request, draft, form, status=400)
        try:
            if action == "send_email_otp":
                code = draft.issue_otp("email")
                draft.save(request)
                self._store_debug(request, "email", code)
                messages.success(request, "We sent a code to your email.")
                draft.set_step("verify")
                draft.save(request)
                return redirect("/merchant/register/?step=verify")
            if action == "send_mobile_otp":
                code = draft.issue_otp("mobile")
                draft.save(request)
                self._store_debug(request, "mobile", code)
                messages.success(request, "We sent a code to your mobile.")
                draft.set_step("verify")
                draft.save(request)
                return redirect("/merchant/register/?step=verify")
            if action == "confirm_email":
                code = _otp_digits(request.POST.get("email_code", ""))
                if len(code) != 6:
                    return self._render(
                        request,
                        draft,
                        MerchantRegisterForm(initial=self._initial(draft)),
                        status=400,
                        otp_error_email="Enter a valid OTP.",
                    )
                if not draft.confirm_otp("email", code):
                    draft.save(request)
                    return self._render(
                        request,
                        draft,
                        MerchantRegisterForm(initial=self._initial(draft)),
                        status=400,
                        otp_error_email="The OTP is incorrect or has expired.",
                    )
                draft.save(request)
                messages.success(request, "Email verified.")
                return redirect("/merchant/register/?step=verify")
            if action == "confirm_mobile":
                code = _otp_digits(request.POST.get("mobile_code", ""))
                if len(code) != 6:
                    return self._render(
                        request,
                        draft,
                        MerchantRegisterForm(initial=self._initial(draft)),
                        status=400,
                        otp_error_mobile="Enter a valid OTP.",
                    )
                if not draft.confirm_otp("mobile", code):
                    draft.save(request)
                    return self._render(
                        request,
                        draft,
                        MerchantRegisterForm(initial=self._initial(draft)),
                        status=400,
                        otp_error_mobile="The OTP is incorrect or has expired.",
                    )
                draft.save(request)
                messages.success(request, "Mobile verified.")
                return redirect("/merchant/register/?step=verify")
            if action == "finish":
                return self._finish(request, draft)
            if step == "details" or action == "continue" and draft.step == "details":
                form = MerchantRegisterForm(request.POST)
                if not form.is_valid():
                    draft.set_step("details")
                    return self._render(request, draft, form, status=400)
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
                if email_code:
                    self._store_debug(request, "email", email_code)
                if mobile_code:
                    self._store_debug(request, "mobile", mobile_code)
                return redirect("/merchant/register/?step=verify")
            if action == "continue" and draft.step == "verify":
                if not draft.can_preview():
                    return self._render(
                        request,
                        draft,
                        MerchantRegisterForm(initial=self._initial(draft)),
                        status=400,
                        otp_error_email="" if draft.data.get("email_verified") else "Email is not verified.",
                        otp_error_mobile=""
                        if draft.data.get("mobile_verified")
                        else "Mobile is not verified.",
                    )
                draft.set_step("preview")
                draft.save(request)
                return redirect("/merchant/register/?step=preview")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            draft.save(request)
        return self._render(request, draft, MerchantRegisterForm(initial=self._initial(draft)), status=400)

    def _finish(self, request, draft: RegistrationDraft):
        if request.POST.get("accept_terms") != "on":
            draft.set_step("preview")
            draft.save(request)
            form = MerchantRegisterForm({})
            form.is_valid()
            form.add_error(
                "accept_terms",
                "Accept the Terms and Conditions and Privacy Policy.",
            )
            return self._render(request, draft, form, status=400)
        if not draft.can_preview() or not draft.data.get("password_hash"):
            raise ValidationError("Complete details and verification before creating the account.")
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
        Policy.grant_role(user, "merchant")
        application = MerchantOnboardingService.start(
            user,
            entity_type=draft.data.get("entity_type") or Merchant.EntityType.INDIVIDUAL,
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
        messages.success(
            request,
            "Account created. Sign in, then finish onboarding: Business (PAN) → People → Bank → Documents → Submit.",
        )
        return redirect(LOGIN_PATH)

    def _render(self, request, draft, form, status=200, otp_error_email="", otp_error_mobile=""):
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "draft": draft,
                "preview": draft.preview(),
                "wizard_steps": draft.stepper(),
                "step": draft.step,
                "debug_email": request.session.get("debug_register_email", "") if settings.DEBUG else "",
                "debug_mobile": request.session.get("debug_register_mobile", "") if settings.DEBUG else "",
                "test_mode": getattr(settings, "AUTH_TEST_MODE", False),
                "otp_error_email": otp_error_email,
                "otp_error_mobile": otp_error_mobile,
                "otp_wait_email": draft.otp_wait_seconds("email"),
                "otp_wait_mobile": draft.otp_wait_seconds("mobile"),
            },
            status=status,
        )

    @staticmethod
    def _initial(draft: RegistrationDraft) -> dict:
        return {
            "name": draft.data.get("name", ""),
            "email": draft.data.get("email", ""),
            "mobile": draft.data.get("mobile", ""),
            "address": draft.data.get("address", ""),
            "pincode": draft.data.get("pincode", ""),
            "entity_type": draft.data.get("entity_type") or Merchant.EntityType.INDIVIDUAL,
        }

    @staticmethod
    def _store_debug(request, channel: str, code: str) -> None:
        if settings.DEBUG:
            request.session[f"debug_register_{channel}"] = code


class PasswordResetRequestView(View):
    template_name = "portals/auth/password_reset.html"

    @method_decorator(ratelimit(key="ip", rate="5/h", method="POST", block=True))
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(portal_home(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {"form": PasswordResetRequestForm()})

    def post(self, request):
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            PasswordResetService.request_reset(email=form.cleaned_data["email"], request=request)
        # Same response whether or not the account exists (no enumeration).
        return render(request, self.template_name, {"form": form, "sent": True})


class PasswordResetConfirmView(View):
    template_name = "portals/auth/password_reset_confirm.html"

    @method_decorator(ratelimit(key="ip", rate="10/h", method="POST", block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, uidb64, token):
        if PasswordResetService.resolve(uidb64, token) is None:
            return render(request, self.template_name, {"invalid": True, "form": PasswordResetConfirmForm()})
        return render(request, self.template_name, {"form": PasswordResetConfirmForm()})

    def post(self, request, uidb64, token):
        form = PasswordResetConfirmForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form}, status=400)
        try:
            PasswordResetService.confirm(
                uidb64=uidb64,
                token=token,
                new_password=form.cleaned_data["password"],
                request=request,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return render(request, self.template_name, {"form": form}, status=400)
        return render(request, self.template_name, {"done": True, "form": PasswordResetConfirmForm()})
