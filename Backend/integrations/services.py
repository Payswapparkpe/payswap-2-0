from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from agreements.esign import record_event
from agreements.models import Agreement
from agreements.pdf import pdf_sha256, render_agreement_pdf
from audit.services import AuditService
from integrations.cashfree import CashfreeClient, CashfreeError, new_verification_id
from merchants.models import Merchant
from verification.models import ConsentRecord
from verification.services import VerificationService


class ESignService:
    """Cashfree Aadhaar eSign for agreements.

    The signing outcome is NEVER derived from the browser redirect: only the
    signature-verified webhook or the Get E-Sign Status API may advance an
    agreement (see agreements.services.EsignStatusService).
    """

    @staticmethod
    def cashfree() -> CashfreeClient:
        return CashfreeClient(
            client_id=getattr(settings, "CASHFREE_CLIENT_ID", ""),
            client_secret=getattr(settings, "CASHFREE_CLIENT_SECRET", ""),
            environment=getattr(settings, "CASHFREE_ENV", "sandbox"),
        )

    @staticmethod
    def start_esign(*, agreement, actor, request=None) -> str:
        """Upload the final PDF, create the signing request, return the signing link."""
        if not getattr(settings, "FEATURE_ESIGN", True):
            raise CashfreeError("eSign is disabled for this environment.", code="feature_disabled")
        # Consent before any Aadhaar-touching flow (§32).
        VerificationService.record_consent(user=actor, purpose=ConsentRecord.Purpose.ESIGN, request=request)
        if agreement.document_file:
            agreement.document_file.open("rb")
            try:
                pdf_bytes = agreement.document_file.read()
            finally:
                agreement.document_file.close()
        else:
            pdf_bytes = render_agreement_pdf(
                title="Voucher Supply & Services Agreement",
                reference=agreement.public_id,
                body=agreement.body,
            )
        if getattr(settings, "AUTH_TEST_MODE", False):
            agreement.document_hash = pdf_sha256(pdf_bytes)
            agreement.document_file.save(f"{agreement.public_id}.pdf", ContentFile(pdf_bytes), save=False)
            agreement.status = Agreement.Status.MERCHANT_SIGNED
            agreement.merchant_signed_at = timezone.now()
            agreement.esign_status = "SUCCESS"
            agreement.save(
                update_fields=[
                    "status",
                    "merchant_signed_at",
                    "esign_status",
                    "document_hash",
                    "document_file",
                ]
            )
            record_event(
                agreement,
                "merchant_signed",
                actor=actor,
                request=request,
                reference=agreement.public_id,
                metadata={"test_mode": True},
            )
            agreement.merchant.agreement_status = Merchant.VerificationState.PENDING
            agreement.merchant.save(update_fields=["agreement_status"])
            AuditService.record(
                actor=actor,
                action="agreement.esign_start",
                resource_type="agreement",
                resource_id=agreement.public_id,
                after={"esign_status": agreement.esign_status, "test_mode": True},
                request=request,
            )
            return ""
        client = ESignService.cashfree()
        uploaded = client.esign_upload_document(filename=f"{agreement.public_id}.pdf", content=pdf_bytes)
        document_id = uploaded.get("document_id")
        if not document_id:
            raise CashfreeError("eSign upload did not return a document id.", code="upload_failed")
        verification_id = new_verification_id("esign")
        created = client.esign_create_request(
            verification_id=verification_id,
            document_id=int(document_id),
            signer_name=actor.name or actor.email,
            signer_email=actor.email,
            signer_phone=getattr(actor, "mobile", "") or "",
        )
        signing_link = str(created.get("signing_link") or "")
        agreement.esign_document_id = str(document_id)
        agreement.esign_verification_id = verification_id
        agreement.esign_request_id = str(created.get("reference_id") or "")
        agreement.esign_status = "SENT"
        # Hash and store the artifact actually sent for signature.
        agreement.document_hash = pdf_sha256(pdf_bytes)
        agreement.document_file.save(f"{agreement.public_id}.pdf", ContentFile(pdf_bytes), save=False)
        agreement.save(
            update_fields=[
                "esign_document_id",
                "esign_verification_id",
                "esign_request_id",
                "esign_status",
                "document_hash",
                "document_file",
            ]
        )
        record_event(
            agreement,
            "sent_for_signature",
            actor=actor,
            request=request,
            reference=agreement.esign_request_id,
            metadata={"verification_id": verification_id},
        )
        AuditService.record(
            actor=actor,
            action="agreement.esign_start",
            resource_type="agreement",
            resource_id=agreement.public_id,
            after={
                "esign_status": agreement.esign_status,
                "reference_id": agreement.esign_request_id,
                "verification_id": verification_id,
            },
            request=request,
        )
        return signing_link
