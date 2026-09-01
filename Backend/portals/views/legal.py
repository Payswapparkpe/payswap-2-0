from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import TemplateView


class LegalPageView(TemplateView):
    extra_context = {}


class PrivacyPolicyView(LegalPageView):
    template_name = "legal/privacy.html"


class TermsView(LegalPageView):
    template_name = "legal/terms.html"


class CookiePolicyView(LegalPageView):
    template_name = "legal/cookies.html"


class GrievanceView(LegalPageView):
    template_name = "legal/grievance.html"


class CookieConsentView(View):
    def post(self, request):
        choice = request.POST.get("consent", "necessary")
        if choice not in {"necessary", "all"}:
            choice = "necessary"
        next_url = request.META.get("HTTP_REFERER", "")
        if not url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = "/"
        response = redirect(next_url)
        response.set_cookie(
            "ps_cookie_consent",
            choice,
            max_age=60 * 60 * 24 * 365,
            samesite="Lax",
            secure=request.is_secure(),
            httponly=False,
        )
        return response
