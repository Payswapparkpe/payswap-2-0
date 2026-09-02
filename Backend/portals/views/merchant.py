import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from accounts.profile import ProfileService
from agreements.models import Agreement
from agreements.services import AgreementService
from agreements.template import (
    render_voucher_supply_agreement,
    verification_blockers,
    verification_complete,
)
from audit.services import AuditService
from catalog.models import Brand, ServiceType, VoucherProduct
from catalog.services import OrderPricingService
from integrations.cashfree import CashfreeError
from integrations.postal import PostalService
from merchants.matching import (
    MATCH_THRESHOLD,
    annotate_documents,
    assert_document_matches_profile,
    profile_gaps,
    profile_identifiers,
)
from merchants.models import Merchant, OnboardingApplication
from merchants.privacy import decrypt_step_data, display_step_data, encrypt_step_data
from merchants.services import MerchantOnboardingService
from merchants.states import (
    ENTITY_BUSINESS_FIELDS,
    FIELD_LABELS,
    OPTIONAL_BUSINESS_FIELDS,
    STEP_FIELDS,
    WIZARD_KEYS,
    WIZARD_PHASES,
    ApplicationStatus,
    StepStatus,
    first_incomplete_wizard_key,
    next_wizard_key,
    normalize_wizard_key,
    prev_wizard_key,
)
from notifications.models import NotificationPreference
from orders.models import OrderStatus, PaymentOrder
from orders.services import PaymentOrderService
from portals.mixins import MerchantRequiredMixin
from portals.routing import merchant_console_url
from portals.pagination import paginate
from verification.digilocker import DigiLockerService
from verification.models import Document, VerificationRecord
from verification.services import DocumentReviewService
from verification.services import VerificationService as DomainVerificationService

logger = logging.getLogger(__name__)


def _own_application(user, public_id=None):
    if public_id:
        application = get_object_or_404(OnboardingApplication, public_id=public_id)
        if application.merchant.owner_id != user.id:
            raise PermissionDenied("You can only access your own application.")
        return application
    return OnboardingApplication.objects.filter(merchant__owner=user).order_by("-created_at").first()


class MerchantDashboardView(MerchantRequiredMixin, View):
    def get(self, request):
        console = getattr(settings, "PUBLIC_CONSOLE_URL", "").strip()
        if console:
            return redirect(merchant_console_url("/app"))
        application = _own_application(request.user)
        merchant = getattr(request.user, "merchant", None)
        hour = timezone.localtime().hour
        greeting = "Good evening"
        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        orders = PaymentOrder.objects.filter(merchant=merchant) if merchant else PaymentOrder.objects.none()
        progress = _wizard_progress(application)
        done_count = sum(1 for item in progress if item["done"])
        return render(
            request,
            "portals/merchant/dashboard.html",
            {
                "greeting": greeting,
                "application": application,
                "merchant": merchant,
                "wizard_progress": progress,
                "wizard_done": done_count,
                "wizard_total": len(progress) or 5,
                "wizard_percent": int((done_count / len(progress)) * 100) if progress else 0,
                "next_action": _merchant_next_action(request.user, application, merchant),
                "open_orders": orders.exclude(
                    status__in=[OrderStatus.APPROVED, OrderStatus.CANCELLED, OrderStatus.REJECTED]
                ).count(),
                "month_orders": orders.filter(created_at__month=timezone.now().month).count(),
                "approved_orders": orders.filter(status=OrderStatus.APPROVED).count(),
                "profile_gaps": profile_gaps(merchant)
                if merchant
                else ["legal name", "PAN", "date of birth"],
                "match_threshold": MATCH_THRESHOLD,
                "can_create_orders": bool(
                    merchant and merchant.commercial_status == Merchant.CommercialStatus.ACTIVE
                ),
            },
        )


class OnboardingStartView(MerchantRequiredMixin, View):
    def get(self, request):
        application = _own_application(request.user)
        return render(
            request,
            "portals/merchant/onboarding_start.html",
            {"application": application, "entity_types": _entity_choices()},
        )

    def post(self, request):
        entity_type = request.POST.get("entity_type", "PRIVATE_LIMITED")
        application = MerchantOnboardingService.start(request.user, entity_type=entity_type)
        return redirect("merchant:onboarding_detail", public_id=application.public_id)


class OnboardingDetailView(MerchantRequiredMixin, View):
    def get(self, request, public_id):
        application = _own_application(request.user, public_id)
        requested = request.GET.get("step")
        if requested and requested not in WIZARD_KEYS:
            return redirect(f"{request.path}?step={normalize_wizard_key(requested)}")
        current_key = requested or first_incomplete_wizard_key(application)
        step = application.steps.get(key=current_key)
        data = display_step_data(step.data)
        plain = decrypt_step_data(step.data)
        if step.key == "business":
            field_names = (
                ENTITY_BUSINESS_FIELDS.get(application.merchant.entity_type, ["legal_name"])
                + OPTIONAL_BUSINESS_FIELDS
            )
        else:
            field_names = STEP_FIELDS.get(step.key, [])
        step_fields = [
            {
                "name": name,
                "label": FIELD_LABELS.get(name, name.replace("_", " ").title()),
                "value": data.get(name, ""),
            }
            for name in field_names
        ]
        preview_body = ""
        summary = []
        if current_key == "review":
            summary = _onboarding_summary(application)
            preview_body, _snapshot = render_voucher_supply_agreement(application.merchant)
        stepper = _wizard_stepper(application, current_key)
        return render(
            request,
            "portals/merchant/onboarding.html",
            {
                "application": application,
                "step": step,
                "step_fields": step_fields,
                "wizard_steps": stepper["steps"],
                "wizard_done": stepper["done"],
                "wizard_total": stepper["total"],
                "wizard_percent": stepper["percent"],
                "prev_key": prev_wizard_key(current_key),
                "next_key": next_wizard_key(current_key),
                "people": plain.get("people") or [],
                "documents": application.merchant.documents.select_related(
                    "reviewed_by", "uploaded_by"
                ).all(),
                "document_types": Document.DocType.choices,
                "summary": summary,
                "agreement_preview": preview_body,
                "document_rows": annotate_documents(
                    application.merchant,
                    application.merchant.documents.select_related("reviewed_by", "uploaded_by").all(),
                ),
                "match_threshold": MATCH_THRESHOLD,
            },
        )

    def post(self, request, public_id):
        application = _own_application(request.user, public_id)
        action = request.POST.get("action", "save")
        step_key = normalize_wizard_key(request.POST.get("step"))
        try:
            if action == "add_person":
                self._add_person(application, request)
                return redirect(f"{request.path}?step=owners")
            if action == "remove_person":
                self._remove_person(application, request)
                return redirect(f"{request.path}?step=owners")
            if action == "upload_document":
                self._upload_document(application, request)
                MerchantOnboardingService.save_step(application, key="documents", actor=request.user, data={})
                return redirect(f"{request.path}?step=documents")
            if action == "submit":
                MerchantOnboardingService.save_step(application, key="review", actor=request.user, data={})
                MerchantOnboardingService.submit(
                    application,
                    actor=request.user,
                    confirmed=request.POST.get("confirmed") == "on",
                    request=request,
                )
                try:
                    DomainVerificationService.verify_collected(
                        merchant=application.merchant, actor=request.user, request=request
                    )
                except (ValidationError, CashfreeError):
                    logger.exception("collected verification failed for %s", application.public_id)
                    messages.info(
                        request,
                        "Application submitted. Identity checks will complete when the verification service is available.",
                    )
                else:
                    messages.success(request, "Application submitted for review.")
                return redirect("merchant:onboarding_detail", public_id=public_id)
            payload = {
                key: value
                for key, value in request.POST.items()
                if key not in {"csrfmiddlewaretoken", "action", "step", "confirmed"}
            }
            if step_key == "owners":
                existing = decrypt_step_data(application.steps.get(key="owners").data)
                if existing.get("people"):
                    payload["people"] = existing["people"]
                if not (payload.get("owner_name") or "").strip():
                    people = payload.get("people") or existing.get("people") or []
                    payload["owner_name"] = existing.get("owner_name") or (
                        people[0].get("name", "") if people else ""
                    )
                if not (payload.get("authorized_signatory") or "").strip():
                    payload["authorized_signatory"] = existing.get("authorized_signatory") or payload.get(
                        "owner_name", ""
                    )
            MerchantOnboardingService.save_step(application, key=step_key, actor=request.user, data=payload)
            if action == "continue":
                nxt = next_wizard_key(step_key)
                if nxt:
                    return redirect(f"{request.path}?step={nxt}")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect(f"{request.path}?step={step_key}")

    @staticmethod
    def _add_person(application, request):
        name = (request.POST.get("person_name") or "").strip()
        if not name:
            raise ValidationError("Enter a valid name.")
        step = application.steps.get(key="owners")
        plain = decrypt_step_data(step.data)
        people = list(plain.get("people") or [])
        person = {
            "name": name,
            "designation": (request.POST.get("person_designation") or "").strip(),
            "percent": (request.POST.get("person_percent") or "").strip(),
            "signatory": request.POST.get("person_signatory") == "on",
        }
        people.append(person)
        plain["people"] = people
        if person["signatory"] or not plain.get("owner_name"):
            plain["owner_name"] = name
            plain["designation"] = person["designation"]
            plain["ownership_percent"] = person["percent"]
        if person["signatory"] or not plain.get("authorized_signatory"):
            plain["authorized_signatory"] = name
        MerchantOnboardingService.save_step(application, key="owners", actor=request.user, data=plain)

    @staticmethod
    def _remove_person(application, request):
        try:
            index = int(request.POST.get("index", "-1"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("That person could not be removed.") from exc
        step = application.steps.get(key="owners")
        plain = decrypt_step_data(step.data)
        people = list(plain.get("people") or [])
        if index < 0 or index >= len(people):
            raise ValidationError("That person could not be removed.")
        people.pop(index)
        plain["people"] = people
        if people:
            signatory = next((row for row in people if row.get("signatory")), people[0])
            plain["owner_name"] = signatory.get("name", "")
            plain["authorized_signatory"] = signatory.get("name", "")
            plain["designation"] = signatory.get("designation", "")
            plain["ownership_percent"] = signatory.get("percent", "")
            MerchantOnboardingService.save_step(application, key="owners", actor=request.user, data=plain)
            return
        step.data = encrypt_step_data({"people": [], "owner_name": "", "authorized_signatory": ""})
        step.status = StepStatus.NOT_STARTED
        step.save(update_fields=["data", "status", "updated_at"])
        application.merchant.owners.all().delete()

    @staticmethod
    def _upload_document(application, request):
        uploaded = request.FILES.get("file")
        if not uploaded:
            raise ValidationError("Choose a file to upload.")
        doc_type = request.POST.get("doc_type", "OTHER")
        document_number = request.POST.get("document_number", "")
        assert_document_matches_profile(
            merchant=application.merchant,
            doc_type=doc_type,
            document_number=document_number,
            holder_name=request.POST.get("holder_name", ""),
        )
        DocumentReviewService.register_upload(
            merchant=application.merchant,
            actor=request.user,
            doc_type=doc_type,
            uploaded_file=uploaded,
            document_number=document_number,
        )


class MerchantOrderListView(MerchantRequiredMixin, View):
    def get(self, request):
        merchant = getattr(request.user, "merchant", None)
        orders = (
            PaymentOrder.objects.filter(merchant=merchant).select_related("product")
            if merchant
            else PaymentOrder.objects.none()
        )
        page, querystring = paginate(request, orders)
        return render(
            request,
            "portals/merchant/orders.html",
            {"orders": page.object_list, "page": page, "querystring": querystring},
        )


@method_decorator(ratelimit(key="user_or_ip", rate="10/m", method="POST", block=True), name="dispatch")
class MerchantOrderCreateView(MerchantRequiredMixin, View):
    def get(self, request):
        service = ServiceType.objects.filter(code="BRANDED_VOUCHER", is_active=True).first()
        brands = (
            Brand.objects.filter(service_type=service, is_active=True) if service else Brand.objects.none()
        )
        products = VoucherProduct.objects.filter(is_active=True).select_related("brand")
        selected_brand = None
        brand_slug = request.GET.get("brand") or ""
        if brand_slug:
            selected_brand = brands.filter(slug=brand_slug).first() if hasattr(brands, "filter") else None
            if selected_brand:
                products = products.filter(brand=selected_brand)
        try:
            step = int(request.GET.get("step") or 1)
        except (TypeError, ValueError):
            step = 1
        step = step if 1 <= step <= 5 else 1
        try:
            product = products.filter(pk=int(request.GET.get("product"))).first()
        except (TypeError, ValueError):
            product = None
        try:
            quantity = max(int(request.GET.get("quantity") or 1), 1)
        except (TypeError, ValueError):
            quantity = 1
        quote = OrderPricingService.quote(product, quantity) if product and quantity >= 1 else None
        if step >= 3 and product is None:
            step = 2
        return render(
            request,
            "portals/merchant/order_create.html",
            {
                "step": step,
                "services": ServiceType.objects.filter(is_active=True),
                "brands": brands,
                "selected_brand": selected_brand,
                "products": products,
                "product": product,
                "idempotency_key": secrets.token_hex(16),
                "quantity": quantity,
                "quote": quote,
            },
        )

    def post(self, request):
        merchant = getattr(request.user, "merchant", None)
        if merchant is None:
            messages.error(request, "Complete your onboarding before creating an order.")
            return redirect("merchant:onboarding")
        product = get_object_or_404(
            VoucherProduct.objects.filter(is_active=True, brand__service_type__is_active=True),
            pk=request.POST.get("product"),
        )
        try:
            quantity = int(request.POST.get("quantity") or 1)
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid quantity.")
            return redirect("merchant:order_create")
        if request.POST.get("action") == "quote":
            quote = OrderPricingService.quote(product, quantity)
            return JsonResponse(
                {
                    "quantity": quote.quantity,
                    "unit_value": str(quote.unit_value),
                    "subtotal": str(quote.subtotal),
                    "fees": str(quote.fees),
                    "tax": str(quote.tax),
                    "total": str(quote.total),
                }
            )
        idempotency_key = request.POST.get("idempotency_key") or None
        try:
            order = PaymentOrderService.create(
                merchant=merchant,
                actor=request.user,
                product=product,
                quantity=quantity,
                idempotency_key=idempotency_key,
            )
            PaymentOrderService.submit(order, actor=request.user, request=request)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("merchant:order_create")
        messages.success(request, "Order submitted for review.")
        return redirect("merchant:order_detail", public_id=order.public_id)


class MerchantOrderDetailView(MerchantRequiredMixin, View):
    def get(self, request, public_id):
        order = get_object_or_404(
            PaymentOrder.objects.prefetch_related("events__actor", "decisions__actor"),
            public_id=public_id,
            merchant__owner=request.user,
        )
        return render(
            request,
            "portals/merchant/order_detail.html",
            {
                "order": order,
                "can_edit": order.status in OrderStatus.MERCHANT_EDITABLE,
                "can_cancel": order.status in OrderStatus.MERCHANT_CANCELLABLE,
                "products": VoucherProduct.objects.filter(is_active=True),
            },
        )

    def post(self, request, public_id):
        order = get_object_or_404(PaymentOrder, public_id=public_id, merchant__owner=request.user)
        action = request.POST.get("action")
        try:
            if action == "submit":
                PaymentOrderService.submit(order, actor=request.user, request=request)
                messages.success(request, "Order submitted for review.")
            elif action == "edit":
                product = get_object_or_404(
                    VoucherProduct.objects.filter(is_active=True), pk=request.POST.get("product")
                )
                try:
                    quantity = int(request.POST.get("quantity") or order.quantity)
                except (TypeError, ValueError):
                    messages.error(request, "Enter a valid quantity.")
                    return redirect("merchant:order_detail", public_id=order.public_id)
                PaymentOrderService.edit_draft(
                    order=order, actor=request.user, product=product, quantity=quantity, request=request
                )
                messages.success(request, "Order updated.")
            elif action == "cancel":
                PaymentOrderService.cancel(
                    order,
                    actor=request.user,
                    reason=request.POST.get("reason", ""),
                    request=request,
                )
                messages.success(request, "Order cancelled.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect("merchant:order_detail", public_id=order.public_id)


class MerchantAgreementView(MerchantRequiredMixin, View):
    def get(self, request):
        merchant = getattr(request.user, "merchant", None)
        agreements = merchant.agreements.prefetch_related("events").all() if merchant else []
        selected = None
        preview_body = ""
        preview_snapshot = {}
        verification_ready = False
        blockers = []
        if merchant:
            verification_ready = verification_complete(merchant)
            blockers = verification_blockers(merchant)
            if verification_ready:
                issued = AgreementService.issue_if_verification_complete(
                    merchant=merchant, actor=request.user, request=request
                )
                if issued:
                    agreements = merchant.agreements.prefetch_related("events").all()
            preview_body, preview_snapshot = render_voucher_supply_agreement(merchant)
            selected_id = request.GET.get("id")
            if selected_id:
                selected = merchant.agreements.filter(public_id=selected_id).first()
            if selected is None:
                selected = merchant.agreements.order_by("-created_at").first()
        return render(
            request,
            "portals/merchant/agreements.html",
            {
                "agreements": agreements,
                "selected": selected,
                "agreement_preview": selected.body if selected else preview_body,
                "preview_snapshot": selected.generated_from if selected else preview_snapshot,
                "is_draft": selected is None,
                "lifecycle": _agreement_lifecycle(selected),
                "verification_ready": verification_ready,
                "verification_blockers": blockers,
            },
        )

    def post(self, request):
        merchant = getattr(request.user, "merchant", None)
        if merchant is None:
            messages.error(request, "Complete your onboarding before managing agreements.")
            return redirect("merchant:onboarding")
        if request.POST.get("action") != "esign":
            messages.error(request, "Agreements must be signed with Aadhaar eSign after KYC verification.")
            return redirect("merchant:agreements")
        # The checkbox is `required`, but that is only enforced in the browser, so
        # eSign consent has to be re-checked here the same way start_aadhaar does.
        if request.POST.get("consent") != "yes":
            messages.error(request, "Confirm you consent to electronic signing before continuing.")
            return redirect("merchant:agreements")
        agreement = merchant.agreements.order_by("-created_at").first()
        if agreement is None:
            messages.error(request, "No agreement is ready to sign yet.")
            return redirect("merchant:agreements")
        try:
            signing_link = AgreementService.start_esign(
                agreement=agreement, actor=request.user, request=request
            )
            if signing_link:
                return redirect(signing_link)
            messages.info(request, "Signing request sent. Check your email for the signing link.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        except CashfreeError:
            logger.exception("eSign failed for agreement %s", agreement.public_id)
            messages.error(request, "Digital signing could not be started. Please try again.")
        return redirect("merchant:agreements")


@method_decorator(ratelimit(key="user_or_ip", rate="15/m", method="POST", block=True), name="post")
class MerchantDocumentView(MerchantRequiredMixin, View):
    def get(self, request):
        merchant = getattr(request.user, "merchant", None)
        documents = merchant.documents.all() if merchant else []
        return render(
            request,
            "portals/merchant/documents.html",
            {
                "documents": documents,
                "document_rows": annotate_documents(merchant, documents) if merchant else [],
                "profile": profile_identifiers(merchant) if merchant else {},
                "profile_gaps": profile_gaps(merchant)
                if merchant
                else ["legal name", "PAN", "date of birth"],
                "match_threshold": MATCH_THRESHOLD,
            },
        )

    def post(self, request):
        merchant = getattr(request.user, "merchant", None)
        if merchant is None:
            messages.error(request, "Start your onboarding before uploading documents.")
            return redirect("merchant:onboarding")
        try:
            uploaded = request.FILES.get("file")
            if uploaded:
                doc_type = request.POST.get("doc_type", "OTHER")
                document_number = request.POST.get("document_number", "")
                assert_document_matches_profile(
                    merchant=merchant,
                    doc_type=doc_type,
                    document_number=document_number,
                    holder_name=request.POST.get("holder_name", ""),
                )
                DocumentReviewService.register_upload(
                    merchant=merchant,
                    actor=request.user,
                    doc_type=doc_type,
                    uploaded_file=uploaded,
                    document_number=document_number,
                )
                messages.success(request, "Document uploaded for review.")
            else:
                messages.error(request, "Choose a file to upload.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect("/merchant/documents/")


class MerchantPincodeLookupView(MerchantRequiredMixin, View):
    """AJAX helper for the onboarding address fields: PIN → district/state."""

    @method_decorator(ratelimit(key="user_or_ip", rate="30/m", method="GET", block=True))
    def get(self, request):
        try:
            result = PostalService.lookup(request.GET.get("pin", ""))
        except ValidationError as exc:
            return JsonResponse({"error": " ".join(exc.messages)}, status=400)
        return JsonResponse(result)


class MerchantProfileView(MerchantRequiredMixin, View):
    @staticmethod
    def _prefs(user):
        pref = getattr(user, "notification_preference", None)
        if pref is None:
            pref, _ = NotificationPreference.objects.get_or_create(user=user)
        return pref

    def get(self, request):
        merchant = getattr(request.user, "merchant", None)
        application = _own_application(request.user)
        profile = profile_identifiers(merchant) if merchant else {}
        locked = bool(
            application
            and application.status not in {ApplicationStatus.DRAFT, ApplicationStatus.CLARIFICATION_REQUIRED}
        )
        return render(
            request,
            "portals/merchant/profile.html",
            {
                "prefs": self._prefs(request.user),
                "merchant": merchant,
                "application": application,
                "profile": profile,
                "profile_gaps": profile_gaps(merchant)
                if merchant
                else ["legal name", "PAN", "date of birth"],
                "entity_types": _entity_choices(),
                "editable": not locked,
                "match_threshold": MATCH_THRESHOLD,
                "document_rows": annotate_documents(merchant, merchant.documents.all()) if merchant else [],
            },
        )

    def post(self, request):
        user = request.user
        action = request.POST.get("action", "profile")
        if action == "preferences":
            pref = self._prefs(user)
            before = {"email_enabled": pref.email_enabled, "sms_enabled": pref.sms_enabled}
            pref.email_enabled = request.POST.get("email_enabled") == "on"
            pref.sms_enabled = request.POST.get("sms_enabled") == "on"
            pref.save(update_fields=["email_enabled", "sms_enabled", "updated_at"])
            AuditService.record(
                actor=user,
                action="notification.preferences",
                resource_type="user",
                resource_id=str(user.pk),
                before=before,
                after={"email_enabled": pref.email_enabled, "sms_enabled": pref.sms_enabled},
                request=request,
            )
            messages.success(request, "Notification preferences saved.")
            return redirect("/merchant/profile/")

        if action == "business":
            return self._save_business_profile(request)

        name = request.POST.get("name", "").strip()[:150]
        mobile = request.POST.get("mobile", "").strip()
        try:
            ProfileService.update_contact(user=user, name=name, mobile=mobile, request=request)
        except ValidationError:
            messages.error(request, "Enter a valid mobile number.")
            return redirect("/merchant/profile/")
        messages.success(request, "Profile updated.")
        return redirect("/merchant/profile/")

    def _save_business_profile(self, request):
        user = request.user
        entity_type = request.POST.get("entity_type", Merchant.EntityType.INDIVIDUAL)
        if entity_type not in {choice[0] for choice in Merchant.EntityType.choices}:
            messages.error(request, "Choose a valid type of business.")
            return redirect("/merchant/profile/")
        pan = (request.POST.get("pan") or "").upper().strip()
        legal_name = (request.POST.get("legal_name") or "").strip()
        owner_dob = (request.POST.get("owner_dob") or "").strip()
        if not legal_name:
            messages.error(request, "Enter a valid legal name.")
            return redirect("/merchant/profile/")
        if not pan:
            messages.error(request, "Enter a valid PAN.")
            return redirect("/merchant/profile/")
        if not owner_dob:
            messages.error(request, "Enter a valid date of birth.")
            return redirect("/merchant/profile/")
        application = MerchantOnboardingService.start(user, entity_type=entity_type)
        data = {
            "legal_name": legal_name,
            "pan": pan,
            "gstin": (request.POST.get("gstin") or "").upper().strip(),
            "cin": (request.POST.get("cin") or "").upper().strip(),
            "llpin": (request.POST.get("llpin") or "").upper().strip(),
            "registered_office": (request.POST.get("registered_office") or "").strip(),
            "pincode": (request.POST.get("pincode") or "").strip(),
        }
        try:
            MerchantOnboardingService.save_step(application, key="business", actor=user, data=data)
            MerchantOnboardingService.save_step(
                application,
                key="owners",
                actor=user,
                data={
                    "owner_name": request.POST.get("owner_name") or user.name or legal_name,
                    "owner_dob": owner_dob,
                    "authorized_signatory": request.POST.get("owner_name") or user.name or legal_name,
                },
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("/merchant/profile/")
        messages.success(
            request, "Business profile saved. Uploaded documents must match these details at 70% or more."
        )
        return redirect("/merchant/profile/")


def _entity_choices():
    return Merchant.EntityType.choices


@method_decorator(ratelimit(key="user_or_ip", rate="30/m", method="POST", block=True), name="post")
class MerchantVerificationCenterView(MerchantRequiredMixin, View):
    """Status dashboard for collected identifiers. Provider calls use stored data."""

    def get(self, request):
        merchant = getattr(request.user, "merchant", None)
        latest = {}
        pending_aadhaar = None
        collected = {}
        if merchant:
            for record in merchant.verification_records.all():
                latest.setdefault(record.verification_type, record)
            pending_aadhaar = (
                merchant.verification_records.filter(
                    verification_type=VerificationRecord.Type.AADHAAR,
                    status__in=[
                        VerificationRecord.Status.PENDING,
                        VerificationRecord.Status.PROCESSING,
                        VerificationRecord.Status.REQUIRES_RETRY,
                    ],
                )
                .order_by("-requested_at")
                .first()
            )
            collected = _collected_identifiers(merchant)
        return render(
            request,
            "portals/merchant/verification.html",
            {
                "merchant": merchant,
                "records": latest,
                "pending_aadhaar": pending_aadhaar,
                "collected": collected,
                "test_mode": getattr(settings, "AUTH_TEST_MODE", False),
            },
        )

    def post(self, request):
        merchant = getattr(request.user, "merchant", None)
        if merchant is None:
            messages.error(request, "Complete onboarding before running verifications.")
            return redirect("merchant:onboarding")
        action = request.POST.get("action", "")
        try:
            if action == "verify_collected":
                records = DomainVerificationService.verify_collected(
                    merchant=merchant, actor=request.user, request=request
                )
                if not records:
                    messages.info(
                        request,
                        "Nothing is ready to verify yet. Finish onboarding so PAN, GSTIN, and bank details are on file.",
                    )
                else:
                    verified = sum(
                        1 for record in records if record.status == VerificationRecord.Status.VERIFIED
                    )
                    messages.success(
                        request,
                        f"Checked {len(records)} collected detail{'s' if len(records) != 1 else ''}"
                        f"{f' — {verified} verified' if verified else ''}.",
                    )
            elif action == "start_aadhaar":
                if request.POST.get("consent") != "yes":
                    raise ValidationError("Consent is required before Aadhaar verification.")
                collected = _collected_identifiers(merchant, plaintext=True)
                aadhaar_number = collected.get("aadhaar") or request.POST.get("aadhaar_number", "")
                if not aadhaar_number:
                    raise ValidationError("Add an Aadhaar number in onboarding (People) before verifying.")
                url = DigiLockerService.start_aadhaar(
                    merchant=merchant,
                    actor=request.user,
                    aadhaar_number=aadhaar_number,
                    request=request,
                )
                if url:
                    return redirect(url)
                messages.success(request, "Aadhaar is already verified for this business.")
            elif action == "refresh_aadhaar":
                record = get_object_or_404(
                    VerificationRecord,
                    public_id=request.POST.get("record", ""),
                    merchant=merchant,
                    verification_type=VerificationRecord.Type.AADHAAR,
                )
                DigiLockerService.sync_status(record=record)
                self._flash(request, record, "Aadhaar")
            else:
                messages.error(request, "Unknown verification action.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        except CashfreeError:
            logger.exception("Verification provider error for merchant %s", merchant.public_id)
            messages.error(request, "Verification could not be completed. Please try again.")
        return redirect("merchant:verification")

    @staticmethod
    def _flash(request, record, label: str):
        if record.reused_from_id:
            messages.success(
                request,
                f"{label} was verified earlier and is valid until {record.expires_at:%d %b %Y}.",
            )
        elif record.status == VerificationRecord.Status.VERIFIED:
            messages.success(request, f"{label} verified successfully.")
        elif record.status == VerificationRecord.Status.PARTIALLY_VERIFIED:
            messages.warning(request, f"{label} partially verified — review the details.")
        elif record.status in {
            VerificationRecord.Status.PENDING,
            VerificationRecord.Status.PROCESSING,
        }:
            messages.info(request, f"{label} verification is in progress.")
        else:
            messages.error(request, record.display_reason or f"{label} could not be verified.")


def _wizard_progress(application):
    if application is None:
        return []
    by_key = {step.key: step.status for step in application.steps.all()}
    items = []
    for key, title, hint in WIZARD_PHASES:
        status = by_key.get(key, StepStatus.NOT_STARTED)
        items.append(
            {
                "key": key,
                "label": title,
                "hint": hint,
                "status": status,
                "done": status == StepStatus.COMPLETE,
                "needs_fix": status in {StepStatus.NEEDS_CORRECTION, StepStatus.REJECTED},
            }
        )
    return items


def _wizard_stepper(application, current_key):
    items = []
    done_count = 0
    for key, title, _hint in WIZARD_PHASES:
        step = application.steps.filter(key=key).first()
        done = step is not None and step.status == StepStatus.COMPLETE
        if done:
            done_count += 1
        state = "current" if key == current_key else ("done" if done else "pending")
        items.append(
            {
                "key": key,
                "label": title,
                "state": state,
                "url": f"?step={key}",
            }
        )
    total = len(WIZARD_PHASES) or 1
    return {
        "steps": items,
        "done": done_count,
        "total": total,
        "percent": int((done_count / total) * 100),
    }


def _onboarding_summary(application):
    labels = {
        "business": "Business",
        "owners": "People",
        "bank": "Bank",
        "documents": "Documents",
    }
    rows = []
    for key, title in labels.items():
        step = application.steps.filter(key=key).first()
        display = display_step_data(step.data if step else {})
        skip = {"people", "notes", "account_last4"}
        fields = [
            {"label": FIELD_LABELS.get(name, name.replace("_", " ").title()), "value": value}
            for name, value in display.items()
            if name not in skip and value
        ]
        if key == "documents":
            count = application.merchant.documents.count()
            fields.append({"label": "Uploaded files", "value": str(count)})
        rows.append(
            {
                "key": key,
                "title": title,
                "fields": fields,
                "complete": step and step.status == StepStatus.COMPLETE,
                "edit_url": f"?step={key}",
            }
        )
    return rows


def _merchant_next_action(user, application, merchant):
    """Single primary CTA for the merchant dashboard."""
    if application is None:
        return {
            "title": "Start onboarding",
            "body": "Choose your business type, then add people, bank, and documents.",
            "cta": "Start onboarding",
            "href": "/merchant/onboarding/",
            "tone": "info",
        }
    if application.status == ApplicationStatus.CLARIFICATION_REQUIRED:
        fix_step = (
            application.steps.filter(status=StepStatus.NEEDS_CORRECTION).order_by("id").first()
            or application.steps.filter(status=StepStatus.REJECTED).order_by("id").first()
        )
        href = f"/merchant/onboarding/{application.public_id}/"
        if fix_step:
            href = f"{href}?step={fix_step.key}"
        return {
            "title": "Action required",
            "body": (fix_step.clarification_message if fix_step and fix_step.clarification_message else None)
            or application.rejection_notes
            or "Update the section our team highlighted, then resubmit.",
            "cta": "Update application",
            "href": href,
            "tone": "warn",
        }
    if application.status == ApplicationStatus.REJECTED:
        return {
            "title": "Application rejected",
            "body": application.rejection_reason
            or application.rejection_notes
            or "Contact support if you need help understanding this decision.",
            "cta": "View application",
            "href": f"/merchant/onboarding/{application.public_id}/",
            "tone": "danger",
        }
    if application.status in {ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW}:
        if merchant and not verification_complete(merchant):
            return {
                "title": "Complete verification",
                "body": "Your application is with our team. You can still run PAN, GSTIN, bank, and DigiLocker checks.",
                "cta": "Open verification",
                "href": "/merchant/verification/",
                "tone": "info",
            }
        return {
            "title": "Under review",
            "body": f"Application {application.public_id} is with our team. We will notify you when it is approved.",
            "cta": "View application",
            "href": f"/merchant/onboarding/{application.public_id}/",
            "tone": "info",
        }
    if application.status == ApplicationStatus.APPROVED:
        if merchant and merchant.commercial_status == Merchant.CommercialStatus.ACTIVE:
            return {
                "title": "You are ready to order",
                "body": "Your account is commercially active. Create a purchase order when you need stock.",
                "cta": "Create purchase order",
                "href": "/merchant/orders/new/",
                "tone": "ok",
            }
        if merchant and merchant.agreement_status != Merchant.VerificationState.VERIFIED:
            return {
                "title": "Sign your agreement",
                "body": "Onboarding is approved. Review and eSign the supply agreement to go commercially active.",
                "cta": "Open agreements",
                "href": "/merchant/agreements/",
                "tone": "ok",
            }
    incomplete = first_incomplete_wizard_key(application) or "business"
    labels = {key: title for key, title, _hint in WIZARD_PHASES}
    return {
        "title": f"Continue {labels.get(incomplete, 'onboarding').lower()}",
        "body": "Finish the remaining sections, then submit for verification.",
        "cta": "Continue onboarding",
        "href": f"/merchant/onboarding/{application.public_id}/?step={incomplete}",
        "tone": "info",
    }


def _collected_identifiers(merchant, plaintext=False):
    application = merchant.applications.order_by("-created_at").first()
    business = {}
    owners = {}
    bank = {}
    if application:
        business_step = application.steps.filter(key="business").first()
        owners_step = application.steps.filter(key="owners").first()
        bank_step = application.steps.filter(key="bank").first()
        loader = decrypt_step_data if plaintext else display_step_data
        business = loader(business_step.data if business_step else {})
        owners = loader(owners_step.data if owners_step else {})
        bank = loader(bank_step.data if bank_step else {})
    return {
        "legal_name": business.get("legal_name") or merchant.business_name,
        "pan": business.get("pan", ""),
        "gstin": business.get("gstin", ""),
        "cin": business.get("cin", ""),
        "llpin": business.get("llpin", ""),
        "owner_name": owners.get("owner_name", ""),
        "owner_dob": owners.get("owner_dob", ""),
        "aadhaar": owners.get("aadhaar", ""),
        "account_holder": bank.get("account_holder", ""),
        "account_number": bank.get("account_number", ""),
        "ifsc": bank.get("ifsc", ""),
        "has_aadhaar": bool(owners.get("aadhaar")),
    }


def _agreement_lifecycle(agreement):
    steps = [
        {"key": "kyc", "label": "KYC verified", "state": "pending"},
        {"key": "review", "label": "Review", "state": "pending"},
        {"key": "esign", "label": "Aadhaar eSign", "state": "pending"},
        {"key": "signed", "label": "Executed", "state": "pending"},
    ]
    if agreement is None:
        steps[0]["state"] = "current"
        return steps
    merchant = agreement.merchant
    if not verification_complete(merchant):
        steps[0]["state"] = "current"
        return steps
    steps[0]["state"] = "done"
    executed = agreement.status in {
        Agreement.Status.EXECUTED,
        Agreement.Status.COUNTERSIGNED,
    }
    if executed:
        for item in steps:
            item["state"] = "done"
        return steps
    if agreement.status == Agreement.Status.MERCHANT_SIGNED:
        steps[1]["state"] = steps[2]["state"] = "done"
        steps[3]["state"] = "current"
        return steps
    if agreement.esign_request_id:
        steps[1]["state"] = "done"
        steps[2]["state"] = "current"
        return steps
    steps[1]["state"] = "current"
    return steps
