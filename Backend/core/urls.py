from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from core.views import healthz, readyz
from integrations.webhooks import CashfreeWebhookView
from portals.routing import LOGIN_PATH, portal_home
from portals.urls import administration_patterns, employee_patterns, merchant_patterns
from portals.views.auth import (
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PortalLogoutView,
    UnifiedLoginView,
)
from portals.views.common import MfaChallengeView, MfaSetupView, ProtectedMediaView
from portals.views.legal import (
    CookieConsentView,
    CookiePolicyView,
    GrievanceView,
    PrivacyPolicyView,
    TermsView,
)


def home(request):
    if request.user.is_authenticated:
        return redirect(portal_home(request.user))
    return redirect(LOGIN_PATH)


urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", home, name="home"),
    path("api/", include("api.urls")),
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path("webhooks/cashfree/", CashfreeWebhookView.as_view(), name="cashfree_webhook"),
    path("login/", UnifiedLoginView.as_view(), name="login"),
    path("logout/", PortalLogoutView.as_view(), name="logout"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("mfa/", MfaChallengeView.as_view(), name="mfa"),
    path("mfa/setup/", MfaSetupView.as_view(), name="mfa_setup"),
    path("administration/", include((administration_patterns, "administration"))),
    path("employee/", include((employee_patterns, "employee"))),
    path("merchant/", include((merchant_patterns, "merchant"))),
    path("legal/privacy/", PrivacyPolicyView.as_view(), name="privacy"),
    path("legal/terms/", TermsView.as_view(), name="terms"),
    path("legal/cookies/", CookiePolicyView.as_view(), name="cookies"),
    path("legal/grievance/", GrievanceView.as_view(), name="grievance"),
    path("legal/cookies/consent/", CookieConsentView.as_view(), name="cookie_consent"),
]

handler400 = "portals.views.errors.bad_request"
handler403 = "portals.views.errors.permission_denied"
handler404 = "portals.views.errors.page_not_found"
handler500 = "portals.views.errors.server_error"

if settings.DEBUG:
    urlpatterns += [
        path("media/<path:path>", ProtectedMediaView.as_view(), name="protected_media"),
    ]
