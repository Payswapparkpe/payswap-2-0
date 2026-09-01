from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django_otp.forms import OTPAuthenticationFormMixin
from unfold.forms import AuthenticationForm
from unfold.sites import UnfoldAdminSite

User = get_user_model()


class PayswapAdminAuthenticationForm(OTPAuthenticationFormMixin, AuthenticationForm):
    otp_device = forms.CharField(required=False, widget=forms.Select)
    otp_token = forms.CharField(
        label=_("Authenticator code"),
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "inputmode": "numeric"}),
    )
    otp_challenge = forms.CharField(required=False)

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff or not (
            user.is_superuser or getattr(user, "user_type", None) == User.UserType.ADMIN
        ):
            raise forms.ValidationError(
                _("This account is not permitted to use Django admin."),
                code="inactive",
            )

    def clean(self):
        cleaned = super().clean()
        user = self.get_user()
        if user and getattr(settings, "ADMIN_REQUIRE_OTP", False):
            self.clean_otp(user)
        return cleaned


class PayswapAdminSite(UnfoldAdminSite):
    site_header = "Payswap"
    site_title = "Payswap admin"
    index_title = "Control plane"
    login_form = PayswapAdminAuthenticationForm
    login_template = "admin/login.html"
    enable_nav_sidebar = True

    def has_permission(self, request):
        user = request.user
        if not user.is_active or not user.is_staff:
            return False
        if not (user.is_superuser or getattr(user, "user_type", None) == User.UserType.ADMIN):
            return False
        if getattr(settings, "ADMIN_REQUIRE_OTP", False):
            is_verified = getattr(user, "is_verified", None)
            return bool(is_verified and is_verified())
        return True
