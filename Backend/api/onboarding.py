from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from integrations.postal import PostalService
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService
from verification.services import DocumentReviewService
from verification.slots import doc_type_for_slot, normalize_slot_id

from .mixins import JsonView, MerchantRequiredMixin, api_error, parse_json
from .serializers import document_payload, onboarding_payload, onboarding_step_data_from_angular


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
        # Angular sends currentStep as the navigation target; step is the screen being saved.
        step = body.get("step") or body.get("completedStep") or body.get("currentStep") or "profile"
        key, data = onboarding_step_data_from_angular(step, body)
        MerchantOnboardingService.save_step(
            application, key=key, actor=request.user, data=data, source_step=step
        )
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
        slot_id = normalize_slot_id(request.POST.get("slotId") or request.POST.get("doc_type") or "")
        if not slot_id:
            return api_error("Missing upload slot.")
        document_number = request.POST.get("document_number") or ""
        try:
            document = DocumentReviewService.register_upload(
                merchant=merchant,
                actor=request.user,
                doc_type=doc_type_for_slot(slot_id),
                uploaded_file=uploaded,
                document_number=document_number,
                slot_id=slot_id,
            )
        except ValidationError as exc:
            return api_error(" ".join(exc.messages))
        return self.ok(document_payload(document))
