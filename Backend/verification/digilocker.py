"""Aadhaar verification via Cashfree DigiLocker (the current supported path —
OTP-based Aadhaar verification was discontinued by Cashfree).

Flow: consent → Create URL (10-min link) → user completes DigiLocker consent →
webhook or Get Status poll → AUTHENTICATED → Get Document → persist encrypted
VerificationRecord. Statuses map onto VerificationRecord.Status; raw payloads
are stored encrypted only.
"""

import json
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from audit.services import AuditService
from core.crypto import encrypt_text, lookup_hash
from integrations.cashfree import CashfreeClient, CashfreeError, new_verification_id
from merchants.models import Merchant
from merchants.services import next_public_id

from .models import ConsentRecord, VerificationRecord
from .services import VerificationService, mask_document, normalize_document

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    "PENDING": VerificationRecord.Status.PENDING,
    "AUTHENTICATED": VerificationRecord.Status.PROCESSING,
    "EXPIRED": VerificationRecord.Status.EXPIRED,
    "CONSENT_DENIED": VerificationRecord.Status.CANCELLED,
    "FAILURE": VerificationRecord.Status.FAILED,
}

EVENT_SUCCESS = "DIGILOCKER_VERIFICATION_SUCCESS"
EVENT_LINK_EXPIRED = "DIGILOCKER_VERIFICATION_LINK_EXPIRED"
EVENT_CONSENT_DENIED = "DIGILOCKER_VERIFICATION_CONSENT_DENIED"
EVENT_CONSENT_EXPIRED = "DIGILOCKER_VERIFICATION_CONSENT_EXPIRED"
EVENT_FAILURE = "DIGILOCKER_VERIFICATION_FAILURE"
HANDLED_EVENTS = {
    EVENT_SUCCESS,
    EVENT_LINK_EXPIRED,
    EVENT_CONSENT_DENIED,
    EVENT_CONSENT_EXPIRED,
    EVENT_FAILURE,
}


class DigiLockerService:
    @staticmethod
    def _client() -> CashfreeClient:
        return CashfreeClient(
            client_id=getattr(settings, "CASHFREE_CLIENT_ID", ""),
            client_secret=getattr(settings, "CASHFREE_CLIENT_SECRET", ""),
            environment=getattr(settings, "CASHFREE_ENV", "sandbox"),
        )

    @staticmethod
    def start_aadhaar(*, merchant, actor, aadhaar_number: str, request=None) -> str:
        """Create a consent URL. Requires prior explicit consent (ConsentRecord)."""
        if not getattr(settings, "FEATURE_DIGILOCKER", True):
            raise ValidationError("Aadhaar verification via DigiLocker is not enabled.")
        normalized = normalize_document(VerificationRecord.Type.AADHAAR, aadhaar_number)
        # 30-day reuse still applies: a verified Aadhaar for this merchant skips
        # a fresh DigiLocker journey entirely.
        reusable = VerificationService.find_reusable(
            merchant=merchant, vtype=VerificationRecord.Type.AADHAAR, normalized=normalized
        )
        if reusable:
            VerificationService.reuse(source=reusable, merchant=merchant, actor=actor, request=request)
            return ""
        VerificationService.record_consent(
            user=actor, purpose=ConsentRecord.Purpose.DIGILOCKER_ACCESS, request=request
        )
        verification_id = new_verification_id("dgl")
        redirect_url = f"{settings.PUBLIC_BASE_URL}/merchant/verification/"
        try:
            created = DigiLockerService._client().digilocker_create_url(
                verification_id=verification_id,
                documents=["AADHAAR"],
                redirect_url=redirect_url,
                user_flow="signup",
            )
        except CashfreeError as exc:
            if exc.retryable:
                raise ValidationError(
                    "Aadhaar verification is temporarily unavailable. Please try again shortly."
                ) from exc
            raise ValidationError(
                "Aadhaar verification could not be started. Check the number and retry."
            ) from exc

        record = VerificationRecord.objects.create(
            merchant=merchant,
            requested_by=actor,
            public_id=next_public_id("VRF", VerificationRecord),
            verification_type=VerificationRecord.Type.AADHAAR,
            verification_id=verification_id,
            reference_id=str(created.get("reference_id") or ""),
            status=VerificationRecord.Status.PENDING,
            document_masked=mask_document(VerificationRecord.Type.AADHAAR, normalized),
        )

        record.document_encrypted = encrypt_text(normalized)
        record.document_hash = lookup_hash(normalized)
        record.save(update_fields=["document_encrypted", "document_hash"])
        record.refresh_from_db()
        AuditService.record(
            actor=actor,
            action="verification.aadhaar.started",
            resource_type="verification",
            resource_id=record.public_id,
            after={"provider_ref": record.reference_id},
            request=request,
        )
        return str(created.get("url") or "")

    @staticmethod
    def _apply_status(record: VerificationRecord, status: str, payload: dict, *, actor_is_system=True):
        mapped = _STATUS_MAP.get(status)
        if mapped is None:
            logger.warning("digilocker unknown status %s for %s", status, record.verification_id)
            return
        record.status = mapped
        record.sub_status = status
        record.last_checked_at = timezone.now()
        record.set_provider_response(payload)
        update = ["status", "sub_status", "last_checked_at", "provider_response_encrypted"]
        if mapped in {
            VerificationRecord.Status.EXPIRED,
            VerificationRecord.Status.CANCELLED,
            VerificationRecord.Status.FAILED,
        }:
            record.completed_at = timezone.now()
            record.failure_reason = {
                "EXPIRED": "The DigiLocker link expired before completion.",
                "CONSENT_DENIED": "Consent was denied on DigiLocker.",
                "FAILURE": "DigiLocker verification failed at the provider.",
            }.get(status, "")[:200]
            update += ["completed_at", "failure_reason"]
        record.save(update_fields=update)

    @staticmethod
    def complete_authenticated(*, record: VerificationRecord, user_details: dict, request=None):
        """Fetch the Aadhaar document and mark the record verified."""
        try:
            document = DigiLockerService._client().digilocker_get_document(
                document_type="AADHAAR", verification_id=record.verification_id
            )
        except CashfreeError:
            logger.exception("digilocker document fetch failed for %s", record.verification_id)
            record.status = VerificationRecord.Status.REQUIRES_RETRY
            record.save(update_fields=["status"])
            return record
        now = timezone.now()
        record.status = VerificationRecord.Status.VERIFIED
        record.sub_status = "DOCUMENT_RETRIEVED"
        record.completed_at = now
        record.expires_at = now + VerificationService.cache_window()
        record.last_checked_at = now
        record.verified_name = str(user_details.get("name") or "")[:150]
        record.verified_dob = str(user_details.get("dob") or "")[:10]
        record.verified_gender = str(user_details.get("gender") or "")[:10]
        address = document.get("address") if isinstance(document, dict) else {}
        if isinstance(address, dict):
            record.verified_address = str(address.get("full") or "")[:500]
            record.verified_state = str(address.get("state") or "")[:60]
            record.verified_district = str(address.get("district") or "")[:60]
            record.verified_pincode = str(address.get("pincode") or "")[:6]
        record.verified_data_encrypted = encrypt_text(
            json.dumps(
                {"user_details": user_details, "document_keys": sorted(document.keys())},
                sort_keys=True,
            )
        )
        record.set_provider_response(document)
        record.save()
        merchant = record.merchant
        merchant.kyc_status = Merchant.VerificationState.VERIFIED
        merchant.save(update_fields=["kyc_status"])
        # Deferred: agreements.services imports merchants.services.next_public_id.
        from agreements.services import AgreementService

        AgreementService.issue_if_verification_complete(merchant=merchant, actor=None)
        AuditService.record(
            actor=None,
            action="verification.aadhaar.verified",
            resource_type="verification",
            resource_id=record.public_id,
            after={"reference_id": record.reference_id},
        )
        return record

    @staticmethod
    def sync_status(*, record: VerificationRecord):
        """Poll-based completion for environments without inbound webhooks."""
        status_payload = DigiLockerService._client().digilocker_get_status(
            verification_id=record.verification_id
        )
        DigiLockerService._apply_status(record, str(status_payload.get("status") or ""), status_payload)
        if record.status == VerificationRecord.Status.PROCESSING:
            DigiLockerService.complete_authenticated(
                record=record, user_details=status_payload.get("user_details") or {}
            )
        return record

    @staticmethod
    def apply_webhook_event(event_type: str, data: dict) -> str:
        verification_id = str(data.get("verification_id") or "")
        if not verification_id:
            return "ignored"
        record = VerificationRecord.objects.filter(
            verification_id=verification_id, verification_type=VerificationRecord.Type.AADHAAR
        ).first()
        if record is None:
            logger.warning("digilocker webhook for unknown verification_id %s", verification_id)
            return "ignored"
        if record.status == VerificationRecord.Status.VERIFIED:
            return "duplicate"
        if event_type == EVENT_SUCCESS:
            DigiLockerService._apply_status(record, "AUTHENTICATED", data)
            DigiLockerService.complete_authenticated(
                record=record, user_details=data.get("user_details") or {}
            )
            return "processed"
        mapped_status = {
            EVENT_LINK_EXPIRED: "EXPIRED",
            EVENT_CONSENT_DENIED: "CONSENT_DENIED",
            EVENT_CONSENT_EXPIRED: "EXPIRED",
            EVENT_FAILURE: "FAILURE",
        }[event_type]
        DigiLockerService._apply_status(record, mapped_status, data)
        AuditService.record(
            actor=None,
            action=f"verification.aadhaar.{mapped_status.lower()}",
            resource_type="verification",
            resource_id=record.public_id,
        )
        return "processed"
