from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from access.policy import Policy
from accounts.models import User, UserSession
from accounts.profile import ProfileService
from accounts.services import (
    MfaService,
    SessionService,
    StepUpService,
    VerificationService,
)
from agreements.esign import record_event
from agreements.models import Agreement
from audit.services import AuditService
from core.ip import client_ip
from notifications.email_service import EmailService
from notifications.models import Notification
from notifications.services import NotificationService
from portals.routing import LOGIN_PATH, portal_home, post_login_url
from portals.search import search
from verification.models import Document


class NotificationListView(LoginRequiredMixin, View):
    def get(self, request):
        items = Notification.objects.filter(user=request.user)[:50]
        return render(
            request,
            "portals/common/notifications.html",
            {
                "notifications": items,
                "can_send_test_email": Policy.can(request.user, "portal.administration"),
            },
        )

    def post(self, request):
        if request.POST.get("action") == "test_email" and Policy.can(request.user, "portal.administration"):
            template = request.POST.get("template") or "generic_notice"
            EmailService.send(
                to=request.user.email,
                template=template,
                context={
                    "user": request.user,
                    "title": "Test email",
                    "body": "This is a test message from PayswapHub.",
                    "reference": "TEST",
                    "action_url": "/administration/",
                },
            )
            messages.success(request, "Test email queued.")
            return redirect(request.path)
        notification = get_object_or_404(Notification, pk=request.POST.get("id"), user=request.user)
        NotificationService.mark_read(notification)
        return redirect(notification.url or request.path)


class SearchView(LoginRequiredMixin, View):
    @method_decorator(ratelimit(key="user_or_ip", rate="30/m", method="GET", block=True))
    def get(self, request):
        query = request.GET.get("q", "")
        results = search(request.user, query)
        return render(request, "portals/common/search.html", {"query": query, "results": results})


class VerifyContactView(LoginRequiredMixin, View):
    channel = "email"

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def _test_mode(self):
        from django.conf import settings

        return getattr(settings, "AUTH_TEST_MODE", False)

    def get(self, request):
        debug_code = ""
        if settings_debug():
            debug_code = request.session.get(f"debug_verify_{self.channel}", "")
        return render(
            request,
            "portals/auth/verify.html",
            {"channel": self.channel, "debug_code": debug_code, "test_mode": self._test_mode()},
        )

    def post(self, request):
        if request.POST.get("action") == "resend":
            try:
                issued = VerificationService.issue(request.user, channel=self.channel)
            except ValidationError as exc:
                return render(
                    request,
                    "portals/auth/verify.html",
                    {
                        "channel": self.channel,
                        "error": " ".join(exc.messages),
                        "test_mode": self._test_mode(),
                    },
                    status=429,
                )
            if settings_debug():
                request.session[f"debug_verify_{self.channel}"] = issued.debug_code
            return redirect(request.path)
        ok = VerificationService.confirm(
            request.user, channel=self.channel, code=request.POST.get("code", "")
        )
        if ok:
            request.session.pop(f"debug_verify_{self.channel}", None)
            messages.success(
                request,
                f"{'Email' if self.channel == 'email' else 'Mobile'} verified. Continue onboarding when you are ready.",
            )
            return redirect(portal_home(request.user))
        return render(
            request,
            "portals/auth/verify.html",
            {
                "channel": self.channel,
                "error": "The OTP is incorrect or has expired.",
                "debug_code": request.session.get(f"debug_verify_{self.channel}", "")
                if settings_debug()
                else "",
                "test_mode": self._test_mode(),
            },
            status=400,
        )


class VerifyEmailView(VerifyContactView):
    channel = "email"


class VerifyMobileView(VerifyContactView):
    channel = "mobile"


class MfaSetupView(LoginRequiredMixin, View):
    def get(self, request):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        device = TOTPDevice.objects.filter(user=request.user, name="authenticator", confirmed=False).first()
        if device is None:
            device, secret = MfaService.enrol(request.user)
        else:
            secret = device.key
        return render(
            request,
            "portals/auth/mfa_setup.html",
            {"secret": secret, "config_url": device.config_url},
        )

    def post(self, request):
        if MfaService.verify(request.user, request.POST.get("token", "")):
            StepUpService.mark(request.session)
            return redirect(portal_home(request.user))
        # No secret in context on failure: the template hides the block and the
        # page regenerates a fresh one on the next GET.
        return render(
            request,
            "portals/auth/mfa_setup.html",
            {"error": "The authenticator code is incorrect."},
            status=400,
        )


class MfaChallengeView(View):
    @method_decorator(ratelimit(key="ip", rate="8/m", method="POST", block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        if not request.session.get("pending_mfa_user"):
            return redirect(LOGIN_PATH)
        return render(request, "portals/auth/mfa_challenge.html")

    def post(self, request):
        from django.contrib.auth import login

        user_id = request.session.get("pending_mfa_user")
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return redirect(LOGIN_PATH)
        if not MfaService.verify(user, request.POST.get("token", "")):
            return render(
                request,
                "portals/auth/mfa_challenge.html",
                {"error": "The authenticator code is incorrect."},
                status=400,
            )
        login(request, user)
        request.session.cycle_key()
        request.session.pop("pending_mfa_user", None)
        StepUpService.mark(request.session)
        SessionService.track(
            user,
            session_key=request.session.session_key,
            ip_address=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        AuditService.record(
            actor=user,
            action="auth.login",
            resource_type="user",
            resource_id=str(user.pk),
            request=request,
            after={"mfa": True},
        )
        from notifications.email_service import EmailService

        EmailService.send_login_alert(
            user=user,
            ip_address=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return redirect(post_login_url(request, user))


class SessionListView(LoginRequiredMixin, View):
    def get(self, request):
        sessions = UserSession.objects.filter(user=request.user)
        return render(request, "portals/common/sessions.html", {"sessions": sessions})

    def post(self, request):
        tracked = get_object_or_404(UserSession, pk=request.POST.get("id"), user=request.user)
        SessionService.revoke(tracked, actor=request.user, request=request)
        return redirect(request.path)


class AccountProfileView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "portals/common/account_profile.html")

    def post(self, request):
        name = (request.POST.get("name") or "").strip()[:150]
        mobile = (request.POST.get("mobile") or "").strip()
        try:
            ProfileService.update_contact(user=request.user, name=name, mobile=mobile, request=request)
        except ValidationError:
            messages.error(request, "Enter a valid mobile number.")
            return render(request, "portals/common/account_profile.html", status=400)
        messages.success(request, "Profile updated.")
        return redirect(request.path)


class SecurityCenterAccountView(LoginRequiredMixin, View):
    """Self-service security centre: MPIN, authenticator, passkeys, sessions."""

    @method_decorator(ratelimit(key="user_or_ip", rate="20/m", method="POST", block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def _context(self, request):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        from accounts.models import LoginEvent, PasskeyCredential, RecoveryCode, SecurityCredential

        credential = SecurityCredential.objects.filter(user=request.user).first()
        return {
            "credential": credential,
            "totp_device": TOTPDevice.objects.filter(
                user=request.user, name="authenticator", confirmed=True
            ).first(),
            "passkeys": PasskeyCredential.objects.filter(user=request.user),
            "recovery_remaining": RecoveryCode.objects.filter(
                user=request.user, used_at__isnull=True
            ).count(),
            "sessions": UserSession.objects.filter(user=request.user, revoked_at__isnull=True),
            "login_events": LoginEvent.objects.filter(user=request.user)[:10],
        }

    def get(self, request):
        return render(request, "portals/common/security_center.html", self._context(request))

    def post(self, request):
        from accounts.services import MfaService, MpinService

        action = request.POST.get("action", "")
        try:
            if action == "set_mpin":
                MpinService.set(request.user, request.POST.get("mpin", ""), request=request)
                messages.success(request, "MPIN enabled.")
            elif action == "change_mpin":
                MpinService.change(
                    request.user,
                    request.POST.get("current_mpin", ""),
                    request.POST.get("new_mpin", ""),
                    request=request,
                )
                messages.success(request, "MPIN changed.")
            elif action == "regenerate_recovery":
                codes = MfaService.generate_recovery_codes(request.user)
                context = self._context(request)
                context["recovery_codes"] = codes
                return render(request, "portals/common/security_center.html", context)
            else:
                messages.error(request, "Unknown security action.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect(request.path)


class SecurityActionView(LoginRequiredMixin, View):
    def post(self, request, user_id):
        Policy.require(request.user, "security.manage")
        target = get_object_or_404(User, pk=user_id)
        action = request.POST.get("action")
        if action == "suspend":
            target.is_active = False
            target.save(update_fields=["is_active"])
        elif action == "force_logout":
            SessionService.revoke_all(target, actor=request.user)
        elif action == "reset_mfa":
            from django_otp.plugins.otp_totp.models import TOTPDevice

            TOTPDevice.objects.filter(user=target).delete()
            target.mfa_enforced = False
            target.save(update_fields=["mfa_enforced"])
        else:
            return redirect("/administration/security/")
        AuditService.record(
            actor=request.user,
            action=f"security.{action}",
            resource_type="user",
            resource_id=str(target.pk),
            request=request,
        )
        return redirect("/administration/security/")


def settings_debug():
    return settings.DEBUG


class DocumentDownloadView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, public_id):
        document = get_object_or_404(Document, public_id=public_id)
        if not Policy.can_download_document(request.user, document.merchant):
            raise PermissionDenied("You do not have access to this document.")
        AuditService.record(
            actor=request.user,
            action="verification.document_download",
            resource_type="document",
            resource_id=document.public_id,
            request=request,
        )
        return FileResponse(document.file.open("rb"), as_attachment=True)


class ProtectedMediaView(LoginRequiredMixin, View):
    """Serve MEDIA files only after a document permission check (DEBUG deployments)."""

    def get(self, request, path):
        document = Document.objects.filter(file=path).select_related("merchant").first()
        if document is None:
            raise Http404("Not found.")
        if not Policy.can_download_document(request.user, document.merchant):
            raise PermissionDenied("You do not have access to this document.")
        return FileResponse(document.file.open("rb"))


class AgreementDownloadView(LoginRequiredMixin, View):
    """Audited agreement download. POST-only: downloads are state-relevant audit
    events, so they must never be triggered by prefetchable GETs."""

    def post(self, request, public_id):
        agreement = get_object_or_404(Agreement.objects.select_related("merchant"), public_id=public_id)
        owns = request.user.is_merchant_user and agreement.merchant.owner_id == request.user.pk
        if not owns and not Policy.can(request.user, "merchant.view", agreement.merchant):
            raise PermissionDenied("You do not have access to this agreement.")
        kind = request.POST.get("kind", "signed")
        file_field = agreement.signed_file if kind == "signed" else agreement.document_file
        if not file_field:
            raise Http404("Document not available.")
        record_event(
            agreement,
            f"downloaded_{kind}",
            actor=request.user,
            request=request,
        )
        AuditService.record(
            actor=request.user,
            action=f"agreement.download.{kind}",
            resource_type="agreement",
            resource_id=agreement.public_id,
            request=request,
        )
        return FileResponse(
            file_field.open("rb"),
            as_attachment=True,
            filename=f"agreement-{agreement.public_id}-{kind}.pdf",
        )


class OrderDocumentView(LoginRequiredMixin, View):
    """Audited purchase-order PDF download. POST-only for the same reason as
    agreement downloads: the event must never be triggered by prefetchable GETs.
    Allowed for the merchant that owns the order and for staff holding any
    order permission (same gate as the employee order page)."""

    _STAFF_PERMISSIONS = (
        "order.review",
        "order.approve",
        "order.reject",
        "order.request_changes",
        "order.cancel",
        "order.amend",
    )

    def post(self, request, public_id):
        from django.http import HttpResponse

        from orders.document import render_po_pdf
        from orders.models import PaymentOrder

        order = get_object_or_404(
            PaymentOrder.objects.select_related("merchant", "product", "product__brand", "submitted_by"),
            public_id=public_id,
        )
        owns = request.user.is_merchant_user and order.merchant.owner_id == request.user.pk
        staff = request.user.user_type in {User.UserType.ADMIN, User.UserType.EMPLOYEE} and any(
            Policy.has_permission(request.user, permission) for permission in self._STAFF_PERMISSIONS
        )
        if not owns and not staff:
            raise PermissionDenied("You do not have access to this purchase order.")
        content = render_po_pdf(order)
        AuditService.record(
            actor=request.user,
            action="order.document_download",
            resource_type="order",
            resource_id=order.public_id,
            request=request,
        )
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="PO-{order.public_id}-r{order.revision}.pdf"'
        return response
