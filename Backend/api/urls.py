from django.urls import include, path

from .agreements_api import AgreementDownloadView, AgreementView
from .auth import AuthLoginView, AuthLogoutView, AuthMeView, AuthPasswordResetView, AuthRegisterView, AuthVerifyView
from .csrf import CsrfView
from .onboarding import (
    OnboardingDocumentView,
    OnboardingPincodeView,
    OnboardingSubmitView,
    OnboardingView,
    VerificationStartView,
    VerificationStatusView,
)
from .orders_api import CatalogQuoteView, CatalogView, OrderDetailView, OrderListCreateView

merchant_urlpatterns = [
    path("auth/register", AuthRegisterView.as_view(), name="merchant_auth_register"),
    path("auth/login", AuthLoginView.as_view(), name="merchant_auth_login"),
    path("auth/logout", AuthLogoutView.as_view(), name="merchant_auth_logout"),
    path("auth/me", AuthMeView.as_view(), name="merchant_auth_me"),
    path("auth/password-reset", AuthPasswordResetView.as_view(), name="merchant_auth_password_reset"),
    path("auth/verify", AuthVerifyView.as_view(), name="merchant_auth_verify"),
    path("onboarding/", OnboardingView.as_view(), name="merchant_onboarding"),
    path("onboarding/submit", OnboardingSubmitView.as_view(), name="merchant_onboarding_submit"),
    path("onboarding/pincode/", OnboardingPincodeView.as_view(), name="merchant_onboarding_pincode"),
    path("onboarding/documents/", OnboardingDocumentView.as_view(), name="merchant_onboarding_documents"),
    path("verification/start", VerificationStartView.as_view(), name="merchant_verification_start"),
    path("verification/status", VerificationStatusView.as_view(), name="merchant_verification_status"),
    path("agreements/", AgreementView.as_view(), name="merchant_agreements"),
    path("agreements/<str:public_id>/download/", AgreementDownloadView.as_view(), name="merchant_agreement_download"),
    path("catalog/", CatalogView.as_view(), name="merchant_catalog"),
    path("catalog/quote", CatalogQuoteView.as_view(), name="merchant_catalog_quote"),
    path("orders/", OrderListCreateView.as_view(), name="merchant_orders"),
    path("orders/<str:public_id>/", OrderDetailView.as_view(), name="merchant_order_detail"),
]

urlpatterns = [
    path("csrf/", CsrfView.as_view(), name="api_csrf"),
    path("merchant/", include((merchant_urlpatterns, "merchant_api"))),
]
