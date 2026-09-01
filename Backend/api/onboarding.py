from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from integrations.postal import PostalService
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService
from verification.services import DocumentReviewService, VerificationService

from .mixins import JsonView, MerchantRequiredMixin, api_error, parse_json
from .serializers import onboarding_payload, onboarding_step_data_from_angular


def _merchant_context(user):
    merchant = getattr(user, "merchant", None)
    application = None
    if merchant:
        application = merchant.applications.exclude(status="REJECTED").order_by("-created_at").first()
    if application is None and merchant is None:
        application = MerchantOnboardingService.start(user, entity_type=Merchant.EntityType.INDIVIDUAL)
        merchant = application.merchant
    return merchant, application


class OnboardingView(MerchantRequiredMixin, JsonView):
    def get(self, request):
        merchant, application = _merchant_context(request.user)
        return self.ok(onboarding_payload(user=request.user, application=application, merchant=merchant))

    def put(self, request):
        body = parse_json(request)
        merchant, application = _merchant_context(request.user)
        step = body.get("currentStep") or body.get("step") or "profile"
        key, data = onboarding_step_data_from_angular(step, body)
        MerchantOnboardingService.save_step(application, key=key, actor=request.user, data=data)
        merchant.refresh_from_db()
        application.refresh_from_db()
        return self.ok(onboarding_payload(user=request.user, application=application, merchant=merchant))


class OnboardingSubmitView(MerchantRequiredMixin, JsonView):
    def post(self, request):
        body = parse_json(request)
        merchant, application = _merchant_context(request.user)
        MerchantOnboardingService.submit(
            application,
            actor=request.user,
            confirmed=bool(body.get("confirmed", True)),
            request=request,
        )
        application.refresh_from_db()
        return self.ok(onboarding_payload(user=request.user, application=application, merchant=merchant))


class OnboardingPincodeView(MerchantRequiredMixin, JsonView):
    @method_decorator(ratelimit(key="user_or_ip", rate="30/m", method="GET", block=True))
    def get(self, request):
        try:
            result = PostalService.lookup(request.GET.get("pin", ""))
        except ValidationError as exc:
            return api_error(" ".join(exc.messages))
        return self.ok(result)


class OnboardingDocumentView(MerchantRequiredMixin, JsonView):
    def post(self, request):
        merchant, _application = _merchant_context(request.user)
        uploaded = request.FILES.get("file")
        if not uploaded:
            return api_error("Choose a file to upload.")
        doc_type = request.POST.get("doc_type") or request.POST.get("slotId") or "OTHER"
        document_number = request.POST.get("document_number") or ""
        document = DocumentReviewService.register_upload(
            merchant=merchant,
            actor=request.user,
            doc_type=doc_type.upper(),
            uploaded_file=uploaded,
            document_number=document_number,
        )
        return self.ok({"publicId": document.public_id, "docType": document.doc_type, "status": document.status})


class VerificationStartView(MerchantRequiredMixin, JsonView):
    def post(self, request):
        body = parse_json(request)
        merchant, application = _merchant_context(request.user)
        kind = (body.get("kind") or "").lower()
        if kind == "pan":
            business = application.steps.get(key="business")
            from merchants.privacy import decrypt_step_data

            data = decrypt_step_data(business.data)
            owners = decrypt_step_data(application.steps.get(key="owners").data)
            record = VerificationService.verify_pan(
                merchant=merchant,
                actor=request.user,
                pan=body.get("pan") or data.get("pan") or "",
                name=body.get("name") or owners.get("owner_name") or request.user.name,
                dob=body.get("dob") or owners.get("owner_dob") or "",
                request=request,
            )
            return self.ok({"publicId": record.public_id, "status": record.status})
        if kind == "gstin":
            record = VerificationService.verify_gstin(
                merchant=merchant,
                actor=request.user,
                gstin=body.get("gstin") or "",
                request=request,
            )
            return self.ok({"publicId": record.public_id, "status": record.status})
        if kind == "bank":
            record = VerificationService.verify_bank(
                merchant=merchant,
                actor=request.user,
                account_number=body.get("accountNumber") or "",
                ifsc=body.get("ifsc") or "",
                name=body.get("name") or merchant.business_name,
                request=request,
            )
            return self.ok({"publicId": record.public_id, "status": record.status})
        if kind == "collected":
            records = VerificationService.verify_collected(merchant=merchant, actor=request.user, request=request)
            return self.ok({"records": [{"publicId": r.public_id, "status": r.status} for r in records]})
        return api_error("Unsupported verification kind.")


class VerificationStatusView(MerchantRequiredMixin, JsonView):
    def get(self, request):
        merchant, _application = _merchant_context(request.user)
        return self.ok(
            {
                "kycStatus": merchant.kyc_status,
                "kybStatus": merchant.kyb_status,
                "bankStatus": merchant.bank_status,
                "agreementStatus": merchant.agreement_status,
                "commercialStatus": merchant.commercial_status,
            }
        )
