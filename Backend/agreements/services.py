from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone

from access.policy import Policy
from audit.services import AuditService
from merchants.models import Merchant
from merchants.services import next_public_id
from notifications.services import NotificationService

from .models import Agreement
from .pdf import pdf_sha256, render_agreement_pdf
from .template import (
    TEMPLATE_VERSION,
    VERIFICATION_REQUIRED_MESSAGE,
    render_voucher_supply_agreement,
    verification_blockers,
    verification_complete,
)

ACTIVE_STATUSES = (
    Agreement.Status.GENERATED,
    Agreement.Status.INTERNAL_REVIEW,
    Agreement.Status.MERCHANT_REVIEW,
    Agreement.Status.MERCHANT_SIGNED,
    Agreement.Status.COUNTERSIGNED,
    Agreement.Status.EXECUTED,
    Agreement.Status.SIGNING_FAILED,
)


class AgreementService:
    @staticmethod
    def require_verified_kyc(merchant: Merchant) -> None:
        merchant.refresh_from_db()
        if verification_complete(merchant):
            return
        blockers = verification_blockers(merchant)
        raise ValidationError(f"{VERIFICATION_REQUIRED_MESSAGE} {'; '.join(blockers)}.")

    @staticmethod
    def _store_source_pdf(agreement: Agreement) -> None:
        title = (agreement.generated_from or {}).get(
            "title", "AGREEMENT FOR SUPPLY OF BRAND VOUCHERS & GIFT CARDS"
        )
        pdf_bytes = render_agreement_pdf(
            title=title,
            reference=agreement.public_id,
            body=agreement.body,
        )
        agreement.document_hash = pdf_sha256(pdf_bytes)
        agreement.document_file.save(f"{agreement.public_id}.pdf", ContentFile(pdf_bytes), save=False)

    @staticmethod
    def _create(*, merchant: Merchant, actor, request=None) -> Agreement:
        body, snapshot = render_voucher_supply_agreement(merchant)
        agreement = Agreement(
            merchant=merchant,
            public_id=next_public_id("AGR", Agreement),
            body=body,
            generated_from=snapshot,
            status=Agreement.Status.MERCHANT_REVIEW,
            template_version=TEMPLATE_VERSION,
        )
        AgreementService._store_source_pdf(agreement)
        agreement.save()
        merchant.agreement_status = Merchant.VerificationState.PENDING
        merchant.save(update_fields=["agreement_status"])
        AuditService.record(
            actor=actor,
            action="agreement.generate",
            resource_type="agreement",
            resource_id=agreement.public_id,
            after={"merchant": merchant.public_id, "template": TEMPLATE_VERSION},
            request=request,
        )
        NotificationService.notify(
            user=merchant.owner,
            title="Agreement ready",
            body="Please review your prefilled service agreement and complete Aadhaar eSign.",
            url="/merchant/agreements/",
            email=True,
            template="agreement_ready",
            context={"reference": agreement.public_id},
        )
        return agreement

    @staticmethod
    def generate(*, merchant: Merchant, actor, request=None) -> Agreement:
        Policy.require(actor, "merchant.review", merchant)
        AgreementService.require_verified_kyc(merchant)
        return AgreementService._create(merchant=merchant, actor=actor, request=request)

    @staticmethod
    def issue_if_verification_complete(*, merchant: Merchant, actor=None, request=None) -> Agreement | None:
        """Idempotent issue after KYC/KYB/bank succeed. No staff policy required."""
        merchant.refresh_from_db()
        if not verification_complete(merchant):
            return None
        existing = merchant.agreements.filter(status__in=ACTIVE_STATUSES).order_by("-created_at").first()
        if existing:
            return existing
        return AgreementService._create(merchant=merchant, actor=actor, request=request)

    @staticmethod
    def merchant_sign(*, agreement: Agreement, actor, request=None):
        raise ValidationError(
            "Agreements must be signed with Aadhaar eSign after KYC verification. Click-wrap signing is not permitted."
        )

    @staticmethod
    def countersign(*, agreement: Agreement, actor, request=None):
        Policy.require(actor, "merchant.review", agreement.merchant)
        if agreement.status != Agreement.Status.MERCHANT_SIGNED:
            raise ValidationError("The merchant must complete Aadhaar eSign before Payswap can countersign.")
        now = timezone.now()
        agreement.status = Agreement.Status.EXECUTED
        agreement.countersigned_at = now
        agreement.executed_at = now
        agreement.save(update_fields=["status", "countersigned_at", "executed_at"])
        merchant = agreement.merchant
        merchant.agreement_status = Merchant.VerificationState.VERIFIED
        merchant.commercial_status = Merchant.CommercialStatus.ACTIVE
        merchant.save(update_fields=["agreement_status", "commercial_status"])
        NotificationService.notify(
            user=merchant.owner,
            title="Agreement in force",
            body="The agreement has been countersigned. Your account is commercially active.",
            url="/merchant/agreements/",
            email=True,
            template="agreement_executed",
            context={"reference": agreement.public_id},
        )
        AuditService.record(
            actor=actor,
            action="agreement.countersign",
            resource_type="agreement",
            resource_id=agreement.public_id,
            request=request,
        )
        return agreement

    @staticmethod
    def start_esign(*, agreement: Agreement, actor, request=None) -> str:
        if agreement.merchant.owner_id != actor.id and getattr(actor, "user_type", "") != "ADMIN":
            raise ValidationError("Only the merchant or an administrator can start eSign.")
        AgreementService.require_verified_kyc(agreement.merchant)
        if agreement.status == Agreement.Status.EXECUTED:
            raise ValidationError("This agreement has already been executed.")
        if agreement.status not in {
            Agreement.Status.MERCHANT_REVIEW,
            Agreement.Status.SIGNING_FAILED,
            Agreement.Status.EXPIRED,
        }:
            raise ValidationError("This agreement is not waiting for merchant eSign.")
        # Deferred: integrations.services imports verification.services.
        from integrations.services import ESignService

        return ESignService.start_esign(agreement=agreement, actor=actor, request=request)
