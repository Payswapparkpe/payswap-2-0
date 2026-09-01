from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from access.models import UserRole
from access.policy import Policy
from accounts.models import User
from audit.services import AuditService
from portals.routing import LOGIN_PATH, MFA_SETUP_PATH


def staff_requires_otp(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "user_type", None) == User.UserType.ADMIN and getattr(
        settings, "ADMIN_REQUIRE_OTP", False
    ):
        return True
    if getattr(user, "user_type", None) != User.UserType.EMPLOYEE:
        return False
    required = set(getattr(settings, "STAFF_REQUIRE_OTP_ROLES", ()) or ())
    if not required:
        return False
    roles = set(UserRole.objects.filter(user=user).values_list("role__slug", flat=True))
    return bool(roles & required)


class PortalRequiredMixin(LoginRequiredMixin):
    portal_action = ""
    login_url = LOGIN_PATH

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not Policy.can(request.user, self.portal_action):
            AuditService.record(
                actor=request.user,
                action="portal.denied",
                resource_type="portal",
                resource_id=self.portal_action,
                result="denied",
                request=request,
            )
            raise PermissionDenied("You do not have access to this portal.")
        return super().dispatch(request, *args, **kwargs)


class AdministrationRequiredMixin(PortalRequiredMixin):
    portal_action = "portal.administration"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if staff_requires_otp(user) and not getattr(user, "mfa_enforced", False):
            return redirect(MFA_SETUP_PATH)
        return super().dispatch(request, *args, **kwargs)


class EmployeeRequiredMixin(PortalRequiredMixin):
    portal_action = "portal.employee"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if staff_requires_otp(user) and not getattr(user, "mfa_enforced", False):
            return redirect(MFA_SETUP_PATH)
        return super().dispatch(request, *args, **kwargs)


class MerchantRequiredMixin(PortalRequiredMixin):
    portal_action = "portal.merchant"


class ActionRequiredMixin:
    required_action = ""

    def dispatch(self, request, *args, **kwargs):
        resource = self.get_policy_resource() if hasattr(self, "get_policy_resource") else None
        Policy.require(request.user, self.required_action, resource)
        return super().dispatch(request, *args, **kwargs)
