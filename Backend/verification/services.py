import json
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access.policy import Policy
from audit.services import AuditService
from core.crypto import encrypt_text, lookup_hash
from core.ip import client_ip
from integrations.cashfree import CashfreeClient, CashfreeError, new_verification_id
from merchants.models import Merchant
from merchants.privacy import decrypt_step_data
from merchants.services import next_public_id
from notifications.services import NotificationService

from .models import BankAccount, ConsentRecord, Document, VerificationRecord
from .names import ALGORITHM_VERSION, match_names
from .providers import CashfreeVerificationProvider, ProviderResult

logger = logging.getLogger(__name__)


def _issue_agreement_if_ready(merchant, actor, request) -> None:
    # Deferred: agreements.services imports merchants.services.next_public_id.
    from agreements.services import AgreementService

    AgreementService.issue_if_verification_complete(merchant=merchant, actor=actor, request=request)


PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
AADHAAR_RE = re.compile(r"^[2-9][0-9]{11}$")

MAX_DAILY_ATTEMPTS = 5  # per merchant + verification type; fresh provider calls only

CONSENT_TEXT_VERSION = "consent-v1"

SAFE_UNAVAILABLE = "Verification is temporarily unavailable. Please try again later."
SAFE_INVALID = "Unable to verify the provided information. Please check your details."
SAFE_ACTION = "Your verification requires additional action."


def user_safe_reason(exc_or_text) -> str:
    """Map provider errors to user-facing copy. Never leak Cashfree payloads."""
    text = str(exc_or_text or "")
    code = str(getattr(exc_or_text, "code", "") or "")
    blob = f"{code} {text}".lower()
    if any(
        token in blob
        for token in (
            "whitelist",
            "rate",
            "timeout",
            "unavailable",
            "transport",
            "503",
            "502",
            "429",
            "not configured",
        )
    ):
        return SAFE_UNAVAILABLE
    if any(token in blob for token in ("action", "consent", "otp", "digilocker")):
        return SAFE_ACTION
    return SAFE_INVALID


def normalize_document(vtype: str, value: str) -> str:
    cleaned = "".join(ch for ch in (value or "") if ch.isalnum()).upper()
    if vtype == VerificationRecord.Type.PAN and not PAN_RE.fullmatch(cleaned):
        raise ValidationError("Enter a valid PAN.")
    if vtype == VerificationRecord.Type.GSTIN and not GSTIN_RE.fullmatch(cleaned):
        raise ValidationError("Enter a valid GSTIN.")
    if vtype == VerificationRecord.Type.IFSC and not IFSC_RE.fullmatch(cleaned):
        raise ValidationError("Enter a valid IFSC.")
    if vtype == VerificationRecord.Type.AADHAAR and not AADHAAR_RE.fullmatch(cleaned):
        raise ValidationError("Enter a valid Aadhaar number.")
    if vtype == VerificationRecord.Type.BANK_ACCOUNT and not (6 <= len(cleaned) <= 40):
        raise ValidationError("Enter a valid account number.")
    return cleaned


def mask_document(vtype: str, normalized: str) -> str:
    if vtype == VerificationRecord.Type.PAN and len(normalized) == 10:
        return f"{normalized[:5]}{'*' * 4}{normalized[-1]}"
    if vtype == VerificationRecord.Type.AADHAAR and len(normalized) == 12:
        return f"XXXXXXXX{normalized[-4:]}"
    if vtype == VerificationRecord.Type.BANK_ACCOUNT:
        return f"XXXXXX{normalized[-4:]}"
    if vtype == VerificationRecord.Type.GSTIN and len(normalized) == 15:
        return f"{normalized[:2]}{'*' * 8}{normalized[-5:]}"
    return normalized if vtype == VerificationRecord.Type.IFSC else f"****{normalized[-4:]}"


class VerificationService:
    """Domain service: normalization, 30-day reuse, provider calls, persistence."""

    @staticmethod
    def provider() -> CashfreeVerificationProvider:
        return CashfreeVerificationProvider(
            CashfreeClient(
                client_id=getattr(settings, "CASHFREE_CLIENT_ID", ""),
                client_secret=getattr(settings, "CASHFREE_CLIENT_SECRET", ""),
                environment=getattr(settings, "CASHFREE_ENV", "sandbox"),
            )
        )

    @staticmethod
    def cache_window() -> timedelta:
        return timedelta(days=getattr(settings, "VERIFICATION_CACHE_DAYS", 30))

    @staticmethod
    def find_reusable(*, merchant, vtype: str, normalized: str, global_scope: bool = False):
        """A record is reusable while ``now < completed_at + cache_window``.

        Boundary: exactly at expiry the record is stale (day 30 at the same
        time-of-day starts a fresh verification). Records created as reuse
        copies are never themselves reuse sources.
        """
        qs = VerificationRecord.objects.filter(
            verification_type=vtype,
            document_hash=lookup_hash(normalized),
            status=VerificationRecord.Status.VERIFIED,
            reused_from__isnull=True,
            expires_at__gt=timezone.now(),
        )  # noqa: E501
        if not global_scope:
            qs = qs.filter(merchant=merchant)
        return qs.order_by("-completed_at").first()

    @staticmethod
    def _daily_attempt_cap_reached(*, merchant, vtype: str) -> bool:
        day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        fresh_calls = VerificationRecord.objects.filter(
            merchant=merchant,
            verification_type=vtype,
            reused_from__isnull=True,
            requested_at__gte=day_start,
        ).count()
        return fresh_calls >= MAX_DAILY_ATTEMPTS

    @classmethod
    def reuse(cls, *, source: VerificationRecord, merchant, actor, request=None) -> VerificationRecord:
        return cls._reuse(source=source, merchant=merchant, actor=actor, request=request)

    @classmethod
    def _reuse(cls, *, source: VerificationRecord, merchant, actor, request=None) -> VerificationRecord:
        now = timezone.now()
        record = VerificationRecord.objects.create(
            merchant=merchant,
            requested_by=actor,
            public_id=next_public_id("VRF", VerificationRecord),
            verification_type=source.verification_type,
            provider=source.provider,
            verification_id=new_verification_id("reuse"),
            reference_id=source.reference_id,
            status=VerificationRecord.Status.VERIFIED,
            document_hash=source.document_hash,
            document_encrypted=source.document_encrypted,
            document_masked=source.document_masked,
            verified_name=source.verified_name,
            verified_dob=source.verified_dob,
            verified_gender=source.verified_gender,
            verified_address=source.verified_address,
            verified_state=source.verified_state,
            verified_city=source.verified_city,
            verified_district=source.verified_district,
            verified_pincode=source.verified_pincode,
            verified_data_encrypted=source.verified_data_encrypted,
            provider_response_encrypted=source.provider_response_encrypted,
            name_match_score=source.name_match_score,
            name_match_category=source.name_match_category,
            reused_from=source,
            reuse_reason="within_cache_window",
            reused_at=now,
            completed_at=now,
            expires_at=source.expires_at,
        )
        AuditService.record(
            actor=actor,
            action=f"verification.{source.verification_type.lower()}.reused",
            resource_type="verification",
            resource_id=record.public_id,
            after={"source": source.public_id, "expires_at": source.expires_at.isoformat()},
            request=request,
        )
        return record

    @classmethod
    def _record_result(
        cls,
        *,
        merchant,
        actor,
        vtype: str,
        normalized: str,
        masked: str,
        result: ProviderResult,
        request=None,
    ) -> VerificationRecord:
        now = timezone.now()
        verified = result.status == VerificationRecord.Status.VERIFIED
        record = VerificationRecord.objects.create(
            merchant=merchant,
            requested_by=actor,
            public_id=next_public_id("VRF", VerificationRecord),
            verification_type=vtype,
            verification_id=new_verification_id(vtype.lower()),
            reference_id=result.reference_id,
            status=result.status,
            verified_name=result.name,
            verified_dob=result.dob,
            verified_gender=result.gender,
            verified_address=result.address,
            verified_state=result.state,
            verified_city=result.city,
            verified_district=result.district,
            verified_pincode=result.pincode,
            name_match_score=result.name_match_score,
            name_match_category=result.name_match_category,
            failure_reason=result.failure_reason[:200],
            completed_at=now,
            expires_at=now + cls.cache_window() if verified else None,
        )
        record.set_document(normalized, masked)
        if result.data:
            record.verified_data_encrypted = encrypt_text(json.dumps(result.data, sort_keys=True))
        if result.raw:
            record.set_provider_response(result.raw)
        record.save()
        AuditService.record(
            actor=actor,
            action=f"verification.{vtype.lower()}",
            resource_type="verification",
            resource_id=record.public_id,
            after={"status": record.status, "reference_id": record.reference_id},
            request=request,
        )
        return record

    @classmethod
    def _run(
        cls,
        *,
        merchant,
        actor,
        vtype: str,
        normalized: str,
        masked: str,
        call,
        request=None,
        global_scope: bool = False,
    ) -> VerificationRecord:
        reusable = cls.find_reusable(
            merchant=merchant, vtype=vtype, normalized=normalized, global_scope=global_scope
        )
        if reusable:
            return cls._reuse(source=reusable, merchant=merchant, actor=actor, request=request)
        if cls._daily_attempt_cap_reached(merchant=merchant, vtype=vtype):
            raise ValidationError(
                "Too many verification attempts today. Please try again tomorrow or contact support."
            )
        with transaction.atomic():
            locked_merchant = Merchant.objects.select_for_update().get(pk=merchant.pk)
            reusable = cls.find_reusable(
                merchant=locked_merchant, vtype=vtype, normalized=normalized, global_scope=global_scope
            )
            if reusable:
                return cls._reuse(source=reusable, merchant=merchant, actor=actor, request=request)
            try:
                result = call()
            except CashfreeError as exc:
                logger.warning(
                    "cashfree verification failed type=%s code=%s status=%s",
                    vtype,
                    exc.code,
                    exc.status,
                )
                if exc.retryable:
                    raise ValidationError(SAFE_UNAVAILABLE) from exc
                result = ProviderResult(
                    status=VerificationRecord.Status.FAILED,
                    failure_reason=user_safe_reason(exc),
                )
            record = cls._record_result(
                merchant=merchant,
                actor=actor,
                vtype=vtype,
                normalized=normalized,
                masked=masked,
                result=result,
                request=request,
            )
        return record

    # ------------------------------------------------------------------
    # Typed entry points
    # ------------------------------------------------------------------
    @classmethod
    def verify_pan(
        cls, *, merchant, actor, pan: str, name: str, dob: str, request=None
    ) -> VerificationRecord:
        normalized = normalize_document(VerificationRecord.Type.PAN, pan)
        if not (name or "").strip():
            raise ValidationError("Enter a valid name.")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", (dob or "").strip()):
            raise ValidationError("Enter a valid date of birth.")
        record = cls._run(
            merchant=merchant,
            actor=actor,
            vtype=VerificationRecord.Type.PAN,
            normalized=normalized,
            masked=mask_document(VerificationRecord.Type.PAN, normalized),
            call=lambda: cls.provider().verify_pan(
                verification_id=new_verification_id("pan"),
                pan=normalized,
                name=name.strip(),
                dob=dob.strip(),
            ),
            request=request,
        )
        if record.status == VerificationRecord.Status.VERIFIED:
            merchant.kyc_status = Merchant.VerificationState.VERIFIED
            merchant.save(update_fields=["kyc_status"])
            _issue_agreement_if_ready(merchant, actor, request)
        return record

    @classmethod
    def check_pan_identity(cls, *, pan: str, name: str, dob: str) -> tuple[bool, str, bool]:
        """Pre-account PAN check. Does not persist a verification record.

        Returns (accepted, message, pending). pending=True means the provider
        was unavailable; the PAN is stored for verification after login.
        """
        try:
            normalized = normalize_document(VerificationRecord.Type.PAN, pan)
        except ValidationError as exc:
            return False, " ".join(exc.messages), False
        if not (name or "").strip():
            return False, "Enter a valid name.", False
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", (dob or "").strip()):
            return False, "Enter a valid date of birth.", False
        if getattr(settings, "AUTH_TEST_MODE", False):
            return True, "PAN accepted.", False
        try:
            result = cls.provider().verify_pan(
                verification_id=new_verification_id("pan"),
                pan=normalized,
                name=name.strip(),
                dob=dob.strip(),
            )
        except CashfreeError as exc:
            reason = user_safe_reason(exc)
            if exc.retryable or "unavailable" in reason.lower():
                return False, reason, True
            return False, reason, False
        if result.status == VerificationRecord.Status.VERIFIED:
            return True, "PAN verified.", False
        return False, result.failure_reason or SAFE_INVALID, False

    @classmethod
    def verify_gstin(cls, *, merchant, actor, gstin: str, request=None) -> VerificationRecord:
        normalized = normalize_document(VerificationRecord.Type.GSTIN, gstin)
        record = cls._run(
            merchant=merchant,
            actor=actor,
            vtype=VerificationRecord.Type.GSTIN,
            normalized=normalized,
            masked=mask_document(VerificationRecord.Type.GSTIN, normalized),
            call=lambda: cls.provider().verify_gstin(gstin=normalized),
            request=request,
        )
        if record.status == VerificationRecord.Status.VERIFIED:
            merchant.kyb_status = Merchant.VerificationState.VERIFIED
            merchant.save(update_fields=["kyb_status"])
            _issue_agreement_if_ready(merchant, actor, request)
        return record
        return record

    @classmethod
    def verify_bank(
        cls, *, merchant, actor, account_number: str, ifsc: str, name: str, request=None
    ) -> VerificationRecord:
        normalized_account = normalize_document(VerificationRecord.Type.BANK_ACCOUNT, account_number)
        normalized_ifsc = normalize_document(VerificationRecord.Type.IFSC, ifsc)
        record = cls._run(
            merchant=merchant,
            actor=actor,
            vtype=VerificationRecord.Type.BANK_ACCOUNT,
            normalized=normalized_account,
            masked=mask_document(VerificationRecord.Type.BANK_ACCOUNT, normalized_account),
            call=lambda: cls.provider().verify_bank(
                account_number=normalized_account,
                ifsc=normalized_ifsc,
                name=name.strip(),
            ),
            request=request,
        )
        account, _ = BankAccount.objects.get_or_create(
            merchant=merchant,
            defaults={
                "account_holder": name.strip(),
                "ifsc": normalized_ifsc,
                "account_number_encrypted": encrypt_text(normalized_account),
            },
        )
        account.account_holder = name.strip()
        account.ifsc = normalized_ifsc
        account.set_account_number(normalized_account)
        account.verified = record.status == VerificationRecord.Status.VERIFIED
        account.provider_ref = record.reference_id
        account.save()
        merchant.bank_status = (
            Merchant.VerificationState.VERIFIED
            if record.status == VerificationRecord.Status.VERIFIED
            else Merchant.VerificationState.PENDING
        )
        merchant.save(update_fields=["bank_status"])
        if record.status == VerificationRecord.Status.VERIFIED:
            _issue_agreement_if_ready(merchant, actor, request)
        return record

    @classmethod
    def verify_ifsc(cls, *, merchant, actor, ifsc: str, request=None) -> VerificationRecord:
        normalized = normalize_document(VerificationRecord.Type.IFSC, ifsc)
        # IFSC metadata is public and stable: reuse across merchants.
        return cls._run(
            merchant=merchant,
            actor=actor,
            vtype=VerificationRecord.Type.IFSC,
            normalized=normalized,
            masked=normalized,
            call=lambda: cls.provider().verify_ifsc(
                verification_id=new_verification_id("ifsc"),
                ifsc=normalized,
            ),
            request=request,
            global_scope=True,
        )

    @classmethod
    def verify_collected(cls, *, merchant, actor, request=None) -> list:
        """Run provider checks against identifiers already stored on the merchant.

        Collect-first: PAN, GSTIN, bank, and IFSC are never re-entered here.
        Missing fields are skipped rather than prompting a second form.
        """
        application = merchant.applications.order_by("-created_at").first()
        business = {}
        owners = {}
        if application:
            business_step = application.steps.filter(key="business").first()
            owners_step = application.steps.filter(key="owners").first()
            business = decrypt_step_data(business_step.data if business_step else {})
            owners = decrypt_step_data(owners_step.data if owners_step else {})
        records = []
        pan = (business.get("pan") or "").strip()
        name = (owners.get("owner_name") or business.get("legal_name") or "").strip()
        dob = (owners.get("owner_dob") or "").strip()
        if pan and name and dob:
            try:
                records.append(
                    cls.verify_pan(
                        merchant=merchant, actor=actor, pan=pan, name=name, dob=dob, request=request
                    )
                )
            except ValidationError:
                logger.info("collected PAN verification skipped for merchant %s", merchant.public_id)
        gstin = (business.get("gstin") or "").strip()
        if gstin:
            try:
                records.append(cls.verify_gstin(merchant=merchant, actor=actor, gstin=gstin, request=request))
            except ValidationError:
                logger.info("collected GSTIN verification skipped for merchant %s", merchant.public_id)
        bank = BankAccount.objects.filter(merchant=merchant).first()
        if bank and bank.account_number_encrypted:
            try:
                records.append(
                    cls.verify_bank(
                        merchant=merchant,
                        actor=actor,
                        account_number=bank.get_account_number(),
                        ifsc=bank.ifsc,
                        name=bank.account_holder or merchant.business_name,
                        request=request,
                    )
                )
            except (ValidationError, ValueError):
                logger.info("collected bank verification skipped for merchant %s", merchant.public_id)
            if bank.ifsc:
                try:
                    records.append(
                        cls.verify_ifsc(merchant=merchant, actor=actor, ifsc=bank.ifsc, request=request)
                    )
                except ValidationError:
                    logger.info("collected IFSC verification skipped for merchant %s", merchant.public_id)
        return records

    @classmethod
    def cross_check_names(
        cls, *, merchant, actor, name_a: str, name_b: str, context: str, request=None
    ) -> VerificationRecord:
        category, score = match_names(name_a, name_b)
        result = ProviderResult(
            status=(
                VerificationRecord.Status.VERIFIED
                if category in {"EXACT", "STRONG_MATCH"}
                else VerificationRecord.Status.FAILED
            ),
            name_match_score=score,
            name_match_category=category,
            data={"context": context, "algorithm": ALGORITHM_VERSION},
        )
        return cls._record_result(
            merchant=merchant,
            actor=actor,
            vtype=VerificationRecord.Type.NAME_MATCH,
            normalized="",
            masked="",
            result=result,
            request=request,
        )

    # ------------------------------------------------------------------
    # Consent
    # ------------------------------------------------------------------
    @staticmethod
    def record_consent(*, user, purpose: str, request=None) -> ConsentRecord:
        consent = ConsentRecord.objects.create(
            user=user,
            purpose=purpose,
            consent_text_version=CONSENT_TEXT_VERSION,
            consent_given=True,
            ip_address=client_ip(request) if request is not None else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request is not None else "")[:255],
            source="portal",
        )
        AuditService.record(
            actor=user,
            action="consent.recorded",
            resource_type="user",
            resource_id=str(user.pk),
            after={"purpose": purpose, "version": CONSENT_TEXT_VERSION},
            request=request,
        )
        return consent


ALLOWED_UPLOAD_TYPES = {
    ".pdf": (b"%PDF", "application/pdf"),
    ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
    ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
}


def validate_document_file(uploaded_file) -> None:
    name = (getattr(uploaded_file, "name", "") or "").lower()
    suffix = ""
    for ext in ALLOWED_UPLOAD_TYPES:
        if name.endswith(ext):
            suffix = ext
            break
    if not suffix:
        raise ValidationError("Upload a PDF, JPEG, or PNG document.")
    magic, _content_type = ALLOWED_UPLOAD_TYPES[suffix]
    header = uploaded_file.read(max(len(magic), 16))
    uploaded_file.seek(0)
    if not header.startswith(magic):
        raise ValidationError("The file contents do not match a PDF, JPEG, or PNG document.")
    content_type = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].strip().lower()
    allowed_types = {item[1] for item in ALLOWED_UPLOAD_TYPES.values()}
    if content_type and content_type not in allowed_types and content_type != "application/octet-stream":
        raise ValidationError("Upload a PDF, JPEG, or PNG document.")


class DocumentReviewService:
    @staticmethod
    def approve(*, document: Document, actor, request=None):
        Policy.require(actor, "kyc.approve", document.merchant)
        document.status = Document.Status.VERIFIED
        document.reviewed_by = actor
        document.save(update_fields=["status", "reviewed_by"])
        AuditService.record(
            actor=actor,
            action="document.approve",
            resource_type="document",
            resource_id=document.public_id,
            request=request,
        )
        return document

    @staticmethod
    def reject(*, document: Document, actor, reason: str, request=None):
        if not reason:
            raise ValidationError("A rejection reason is required.")
        Policy.require(actor, "kyc.approve", document.merchant)
        document.status = Document.Status.REJECTED
        document.rejection_reason = reason
        document.reviewed_by = actor
        document.save(update_fields=["status", "rejection_reason", "reviewed_by"])
        NotificationService.notify(
            user=document.merchant.owner,
            title="Document rejected",
            body="A submitted document was rejected. Sign in to replace it.",
            url="/merchant/documents/",
            email=True,
            template="document_rejected",
            context={"reference": document.public_id, "reason": reason},
            request=request,
        )
        AuditService.record(
            actor=actor,
            action="document.reject",
            resource_type="document",
            resource_id=document.public_id,
            reason=reason,
            request=request,
        )
        return document

    @staticmethod
    def request_replacement(*, document: Document, actor, reason: str):
        Policy.require(actor, "kyc.approve", document.merchant)
        document.status = Document.Status.ACTION_REQUIRED
        document.rejection_reason = reason
        document.save(update_fields=["status", "rejection_reason"])
        document.merchant.kyc_status = Merchant.VerificationState.ACTION_REQUIRED
        document.merchant.save(update_fields=["kyc_status"])
        NotificationService.notify(
            user=document.merchant.owner,
            title="Replace a document",
            body="Please replace a submitted document.",
            url="/merchant/documents/",
            email=True,
            template="document_replacement",
            context={"reference": document.public_id, "reason": reason},
        )
        return document

    @staticmethod
    def register_upload(*, merchant, actor, doc_type, uploaded_file=None, document_number="") -> Document:
        document = Document(
            merchant=merchant,
            public_id=next_public_id("DOC", Document),
            doc_type=doc_type,
            uploaded_by=actor,
            status=Document.Status.UNDER_REVIEW,
        )
        if uploaded_file:
            validate_document_file(uploaded_file)
            document.file = uploaded_file
        if document_number:
            document.set_document_number(document_number)
        document.save()
        AuditService.record(
            actor=actor,
            action="document.upload",
            resource_type="document",
            resource_id=document.public_id,
            after={"doc_type": doc_type},
        )
        return document
