"""Authoritative eSign status handling for agreements.

The browser returning from Cashfree's hosted signing page is NEVER trusted.
Only two sources may advance an agreement: the signature-verified webhook and
the Get E-Sign Status API. On a verified SUCCESS we fetch ``signed_doc_url``,
download the signed PDF, verify it parses as a PDF, store it, and hash it.
"""

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone

from audit.services import AuditService
from core.ip import client_ip
from integrations.cashfree import CashfreeClient, CashfreeError
from merchants.models import Merchant
from notifications.services import NotificationService

from .models import Agreement, AgreementEvent
from .pdf import pdf_sha256

logger = logging.getLogger(__name__)

EVENT_SUCCESS = "E_SIGN_VERIFICATION_SUCCESS"
EVENT_FAILURE = "E_SIGN_VERIFICATION_FAILURE"
EVENT_EXPIRED = "E_SIGN_VERIFICATION_EXPIRED"
HANDLED_EVENTS = {EVENT_SUCCESS, EVENT_FAILURE, EVENT_EXPIRED}

_ESIGN_TO_AGREEMENT = {
    "IN_PROGRESS": None,  # no lifecycle change; esign_status only
    "SUCCESS": Agreement.Status.MERCHANT_SIGNED,
    "EXPIRED": Agreement.Status.EXPIRED,
    "FAILURE": Agreement.Status.SIGNING_FAILED,
}


def record_event(agreement: Agreement, event: str, *, actor=None, request=None, reference="", metadata=None):
    AgreementEvent.objects.create(
        agreement=agreement,
        event=event,
        actor=actor,
        ip_address=client_ip(request) if request is not None else None,
        user_agent=(request.META.get("HTTP_USER_AGENT", "") if request is not None else "")[:255],
        reference=reference[:80],
        metadata=metadata or {},
    )


class EsignStatusService:
    @staticmethod
    def _client() -> CashfreeClient:
        return CashfreeClient(
            client_id=getattr(settings, "CASHFREE_CLIENT_ID", ""),
            client_secret=getattr(settings, "CASHFREE_CLIENT_SECRET", ""),
            environment=getattr(settings, "CASHFREE_ENV", "sandbox"),
        )

    @staticmethod
    def _store_signed_document(agreement: Agreement, signed_doc_url: str) -> None:
        content = EsignStatusService._client().download_signed_document(signed_doc_url)
        if not content.startswith(b"%PDF"):
            raise CashfreeError("Signed document is not a PDF.", code="invalid_document")
        agreement.signed_file.save(f"{agreement.public_id}-signed.pdf", ContentFile(content), save=False)
        agreement.signed_document_hash = pdf_sha256(content)
        record_event(
            agreement,
            "signed_document_received",
            reference=agreement.esign_request_id,
            metadata={"sha256": agreement.signed_document_hash, "bytes": len(content)},
        )

    @staticmethod
    def refresh(agreement: Agreement) -> Agreement:
        """Authoritative poll: Get E-Sign Status by verification_id/reference_id."""
        if not (agreement.esign_verification_id or agreement.esign_request_id):
            raise ValidationError("No eSign request exists for this agreement.")
        status_payload = EsignStatusService._client().esign_get_status(
            verification_id=agreement.esign_verification_id,
            reference_id=agreement.esign_request_id,
        )
        return EsignStatusService._apply(agreement, status_payload, source="status_api")

    @staticmethod
    def _apply(agreement: Agreement, payload: dict, *, source: str) -> Agreement:
        esign_status = str(payload.get("status") or "").upper()
        previous = agreement.esign_status
        agreement.esign_status = esign_status or previous
        agreement.save(update_fields=["esign_status"])
        if esign_status != previous:
            record_event(
                agreement,
                f"esign_{esign_status.lower() or 'unknown'}",
                reference=str(payload.get("reference_id") or agreement.esign_request_id),
                metadata={"source": source},
            )
        target = _ESIGN_TO_AGREEMENT.get(esign_status)
        if target is None or agreement.status == target:
            return agreement
        if target == Agreement.Status.MERCHANT_SIGNED:
            if agreement.status in {
                Agreement.Status.EXECUTED,
                Agreement.Status.MERCHANT_SIGNED,
                Agreement.Status.COUNTERSIGNED,
            }:
                return agreement
            signed_url = str(payload.get("signed_doc_url") or "")
            if not signed_url:
                # Status said signed but there is no document — retry via poll.
                logger.warning("esign SUCCESS without signed_doc_url for %s", agreement.public_id)
                return agreement
            EsignStatusService._store_signed_document(agreement, signed_url)
            agreement.status = Agreement.Status.MERCHANT_SIGNED
            agreement.merchant_signed_at = timezone.now()
            agreement.save(
                update_fields=["status", "merchant_signed_at", "signed_file", "signed_document_hash"]
            )
            record_event(agreement, "signature_completed", reference=agreement.esign_request_id)
            AuditService.record(
                actor=None,
                action="agreement.signed",
                resource_type="agreement",
                resource_id=agreement.public_id,
                after={"source": source, "hash": agreement.signed_document_hash},
            )
            NotificationService.notify(
                user=agreement.merchant.owner,
                title="Agreement signed",
                body="Aadhaar eSign completed. Payswap will countersign next.",
                url="/merchant/agreements/",
                email=True,
                template="agreement_executed",
                context={"reference": agreement.public_id},
            )
            merchant = agreement.merchant
            merchant.agreement_status = Merchant.VerificationState.PENDING
            merchant.save(update_fields=["agreement_status"])
        elif target in {Agreement.Status.EXPIRED, Agreement.Status.SIGNING_FAILED}:
            agreement.status = target
            agreement.save(update_fields=["status"])
            AuditService.record(
                actor=None,
                action=f"agreement.{target.lower()}",
                resource_type="agreement",
                resource_id=agreement.public_id,
            )
            NotificationService.notify(
                user=agreement.merchant.owner,
                title="Agreement eSign did not complete",
                body="eSign did not complete. Sign in to retry.",
                url="/merchant/agreements/",
                email=True,
                template="agreement_esign_failed",
                context={"reference": agreement.public_id, "reason": target},
            )
        return agreement

    @staticmethod
    def apply_webhook_event(event_type: str, data: dict) -> str:
        verification_id = str(data.get("verification_id") or "")
        if not verification_id:
            return "ignored"
        agreement = Agreement.objects.filter(esign_verification_id=verification_id).first()
        if agreement is None:
            logger.warning("esign webhook for unknown verification_id %s", verification_id)
            return "ignored"
        record_event(
            agreement, f"webhook_{event_type.lower()}", reference=str(data.get("reference_id") or "")
        )
        if event_type in {EVENT_FAILURE, EVENT_EXPIRED}:
            EsignStatusService._apply(
                agreement,
                {"status": "FAILURE" if event_type == EVENT_FAILURE else "EXPIRED"},
                source="webhook",
            )
            return "processed"
        # SUCCESS: confirm against the status API before trusting the outcome.
        try:
            EsignStatusService.refresh(agreement)
        except (CashfreeError, ValidationError):
            logger.exception("esign status refresh failed after webhook for %s", agreement.public_id)
            return "failed"
        return "processed"
