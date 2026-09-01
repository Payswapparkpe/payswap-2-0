from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404

from agreements.models import Agreement
from agreements.services import AgreementService

from .mixins import JsonView, MerchantRequiredMixin, api_error, parse_json
from .serializers import agreement_payload, onboarding_payload
from .onboarding import _merchant_context


class AgreementView(MerchantRequiredMixin, JsonView):
    def get(self, request):
        merchant, application = _merchant_context(request.user)
        agreement = merchant.agreements.order_by("-created_at").first()
        if agreement is None:
            agreement = AgreementService.issue_if_verification_complete(
                merchant=merchant,
                actor=request.user,
                request=request,
            )
        payload = onboarding_payload(user=request.user, application=application, merchant=merchant)
        if agreement:
            payload["agreementDetail"] = agreement_payload(agreement)
        return self.ok(payload)

    def post(self, request):
        body = parse_json(request)
        merchant, application = _merchant_context(request.user)
        agreement = merchant.agreements.order_by("-created_at").first()
        if agreement is None:
            try:
                agreement = AgreementService.generate(merchant=merchant, actor=request.user, request=request)
            except ValidationError as exc:
                return api_error(" ".join(exc.messages))
        action = body.get("action") or "start_esign"
        if action == "start_esign":
            try:
                redirect_url = AgreementService.start_esign(
                    agreement=agreement,
                    actor=request.user,
                    request=request,
                )
                payload = onboarding_payload(user=request.user, application=application, merchant=merchant)
                payload["redirectUrl"] = redirect_url
                return self.ok(payload)
            except ValidationError as exc:
                return api_error(" ".join(exc.messages))
        return api_error("Unsupported agreement action.")


class AgreementDownloadView(MerchantRequiredMixin, JsonView):
    def get(self, request, public_id):
        merchant = getattr(request.user, "merchant", None)
        if merchant is None:
            raise Http404
        agreement = Agreement.objects.filter(public_id=public_id, merchant=merchant).first()
        if agreement is None or not agreement.document_file:
            raise Http404
        return FileResponse(agreement.document_file.open("rb"), as_attachment=True, filename=f"{public_id}.pdf")
