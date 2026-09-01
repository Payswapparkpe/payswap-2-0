import json

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.crypto import decrypt_text, encrypt_text, lookup_hash


class Document(models.Model):
    class DocType(models.TextChoices):
        PAN = "PAN", "PAN Card"
        GST = "GST", "GST Certificate"
        AADHAAR = "AADHAAR", "Aadhaar"
        COI = "COI", "Certificate of Incorporation"
        BANK_PROOF = "BANK_PROOF", "Bank Proof"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Uploaded"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        VERIFIED = "VERIFIED", "Verified"
        ACTION_REQUIRED = "ACTION_REQUIRED", "Action required"
        REJECTED = "REJECTED", "Rejected"

    merchant = models.ForeignKey("merchants.Merchant", on_delete=models.CASCADE, related_name="documents")
    public_id = models.CharField(max_length=20, unique=True)
    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    file = models.FileField(upload_to="documents/%Y/%m/", blank=True)
    document_number_encrypted = models.TextField(blank=True)
    document_last4 = models.CharField(max_length=4, blank=True)
    provider_ref = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    version = models.PositiveIntegerField(default=1)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_documents",
    )
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["merchant", "status"]),
            models.Index(fields=["doc_type", "status"]),
        ]

    def set_document_number(self, value: str):
        cleaned = "".join(ch for ch in (value or "") if ch.isalnum()).upper()
        self.document_number_encrypted = encrypt_text(cleaned) if cleaned else ""
        self.document_last4 = cleaned[-4:] if cleaned else ""

    def get_document_number(self) -> str:
        if not self.document_number_encrypted:
            return ""
        return decrypt_text(self.document_number_encrypted)


class IdentityCheck(models.Model):
    class Kind(models.TextChoices):
        PAN = "PAN", "PAN"
        GSTIN = "GSTIN", "GSTIN"
        AADHAAR = "AADHAAR", "Aadhaar"
        BANK = "BANK", "Bank account"
        CIN = "CIN", "CIN"

    class Status(models.TextChoices):
        MATCH = "MATCH", "Match"
        MISMATCH = "MISMATCH", "Mismatch"
        PENDING = "PENDING", "Pending"
        ERROR = "ERROR", "Error"

    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="identity_checks"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    document_last4 = models.CharField(max_length=4, blank=True)
    provider = models.CharField(max_length=20, default="cashfree")
    provider_ref = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    name_at_source = models.CharField(max_length=150, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class BankAccount(models.Model):
    merchant = models.OneToOneField(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="bank_account"
    )
    account_holder = models.CharField(max_length=150)
    ifsc = models.CharField(max_length=11)
    account_number_encrypted = models.TextField()
    provider_ref = models.CharField(max_length=64, blank=True)
    verified = models.BooleanField(default=False)

    def set_account_number(self, value: str):
        self.account_number_encrypted = encrypt_text(value)

    def get_account_number(self) -> str:
        return decrypt_text(self.account_number_encrypted)


class VerificationRecord(models.Model):
    """Canonical store for provider identity/business verifications.

    Sensitive identifiers live in three derived forms: ``document_encrypted``
    (Fernet, for provider re-submission), ``document_hash`` (keyed HMAC, for
    deterministic 30-day reuse lookup), and ``document_masked`` (display only).
    Raw provider payloads are encrypted before persistence.
    """

    class Type(models.TextChoices):
        PAN = "PAN", "PAN"
        AADHAAR = "AADHAAR", "Aadhaar"
        GSTIN = "GSTIN", "GSTIN"
        BANK_ACCOUNT = "BANK_ACCOUNT", "Bank account"
        IFSC = "IFSC", "IFSC"
        CIN = "CIN", "CIN"
        NAME_MATCH = "NAME_MATCH", "Name match"
        DIGILOCKER = "DIGILOCKER", "DigiLocker"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        VERIFIED = "VERIFIED", "Verified"
        PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED", "Partially verified"
        FAILED = "FAILED", "Failed"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"
        REQUIRES_ACTION = "REQUIRES_ACTION", "Requires action"
        REQUIRES_RETRY = "REQUIRES_RETRY", "Requires retry"

    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="verification_records"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="verification_records"
    )
    public_id = models.CharField(max_length=20, unique=True)
    verification_type = models.CharField(max_length=20, choices=Type.choices)
    provider = models.CharField(max_length=20, default="cashfree")
    # Our idempotency key sent to the provider (V2 APIs reject duplicates with 409).
    verification_id = models.CharField(max_length=50, unique=True)
    reference_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    sub_status = models.CharField(max_length=60, blank=True)
    document_hash = models.CharField(max_length=64, db_index=True)
    document_encrypted = models.TextField(blank=True)
    document_masked = models.CharField(max_length=40, blank=True)
    verified_name = models.CharField(max_length=150, blank=True)
    verified_dob = models.CharField(max_length=10, blank=True)
    verified_gender = models.CharField(max_length=10, blank=True)
    verified_address = models.TextField(blank=True)
    verified_state = models.CharField(max_length=60, blank=True)
    verified_city = models.CharField(max_length=60, blank=True)
    verified_district = models.CharField(max_length=60, blank=True)
    verified_pincode = models.CharField(max_length=6, blank=True)
    verified_data_encrypted = models.TextField(blank=True)
    provider_response_encrypted = models.TextField(blank=True)
    name_match_score = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    name_match_category = models.CharField(max_length=30, blank=True)
    failure_reason = models.CharField(max_length=200, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=1)
    reused_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reuses"
    )
    reuse_reason = models.CharField(max_length=60, blank=True)
    reused_at = models.DateTimeField(null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["verification_type", "document_hash"]),
            models.Index(fields=["merchant", "verification_type"]),
            models.Index(fields=["requested_by", "verification_type"]),
            models.Index(fields=["reference_id"]),
            models.Index(fields=["status", "requested_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.public_id} {self.verification_type} {self.status}"

    @property
    def display_reason(self) -> str:
        """User-facing failure copy. Historical Cashfree payloads are sanitised."""
        raw = self.failure_reason or ""
        blob = raw.lower()
        if any(token in blob for token in ("whitelist", "cashfree", "http", "x-client", "api.")):
            return "Verification is temporarily unavailable. Please try again later."
        return raw

    def set_document(self, normalized: str, masked: str):
        self.document_encrypted = encrypt_text(normalized)
        self.document_hash = lookup_hash(normalized)
        self.document_masked = masked

    def get_document(self) -> str:
        return decrypt_text(self.document_encrypted)

    def set_provider_response(self, payload: dict):
        self.provider_response_encrypted = encrypt_text(json.dumps(payload, sort_keys=True))

    def get_provider_response(self) -> dict:
        raw = decrypt_text(self.provider_response_encrypted)
        return json.loads(raw) if raw else {}

    @property
    def is_reusable(self) -> bool:
        return (
            self.status == self.Status.VERIFIED
            and self.reused_from_id is None
            and self.expires_at is not None
            and self.expires_at > timezone.now()
        )


class ConsentRecord(models.Model):
    """Consent evidence for sensitive identity processing (DPDPA-conscious).

    Recorded before Aadhaar/DigiLocker/eSign flows begin; consent text is
    versioned so the exact wording the user agreed to is reproducible.
    """

    class Purpose(models.TextChoices):
        AADHAAR_VERIFICATION = "aadhaar_verification", "Aadhaar verification"
        DIGILOCKER_ACCESS = "digilocker_access", "DigiLocker access"
        ESIGN = "esign", "Aadhaar eSign"
        KYC = "kyc", "KYC processing"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="consents")
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    consent_text_version = models.CharField(max_length=20)
    consent_given = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=40, default="portal")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose", "created_at"]),
        ]
