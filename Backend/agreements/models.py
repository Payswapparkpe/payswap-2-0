from django.conf import settings
from django.db import models


class Agreement(models.Model):
    class Status(models.TextChoices):
        GENERATED = "GENERATED", "Generated"
        INTERNAL_REVIEW = "INTERNAL_REVIEW", "Internal review"
        MERCHANT_REVIEW = "MERCHANT_REVIEW", "Merchant review"
        MERCHANT_SIGNED = "MERCHANT_SIGNED", "Merchant signed"
        COUNTERSIGNED = "COUNTERSIGNED", "Countersigned"
        EXECUTED = "EXECUTED", "Executed"
        EXPIRED = "EXPIRED", "Expired"
        SIGNING_FAILED = "SIGNING_FAILED", "Signing failed"
        CANCELLED = "CANCELLED", "Cancelled"

    merchant = models.ForeignKey("merchants.Merchant", on_delete=models.CASCADE, related_name="agreements")
    public_id = models.CharField(max_length=20, unique=True)
    version = models.CharField(max_length=10, default="1.0")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.GENERATED)
    body = models.TextField()
    document_hash = models.CharField(max_length=64, blank=True)
    template_version = models.CharField(max_length=40, blank=True)
    document_file = models.FileField(upload_to="agreements/source/%Y/%m/", blank=True)
    signed_file = models.FileField(upload_to="agreements/signed/%Y/%m/", blank=True)
    signed_document_hash = models.CharField(max_length=64, blank=True)
    esign_document_id = models.CharField(max_length=64, blank=True)
    # Our idempotency key for the eSign request (verification_id).
    esign_verification_id = models.CharField(max_length=50, blank=True, db_index=True)
    # Cashfree's reference_id for the eSign request.
    esign_request_id = models.CharField(max_length=64, blank=True)
    esign_status = models.CharField(max_length=30, blank=True)
    generated_from = models.JSONField(default=dict, blank=True)
    merchant_signed_at = models.DateTimeField(null=True, blank=True)
    countersigned_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["merchant", "status"]),
        ]


class AgreementEvent(models.Model):
    """Append-only agreement timeline (generated → sent → signed → executed)."""

    agreement = models.ForeignKey(Agreement, on_delete=models.CASCADE, related_name="events")
    event = models.CharField(max_length=40)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["agreement", "created_at"]),
        ]
