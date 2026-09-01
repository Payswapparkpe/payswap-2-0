from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80, db_index=True)
    resource_type = models.CharField(max_length=80, blank=True)
    resource_id = models.CharField(max_length=80, blank=True)
    result = models.CharField(max_length=20, default="success")
    reason = models.TextField(blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["request_id"]),
            models.Index(fields=["created_at"]),
        ]


class PublicIdSequence(models.Model):
    """Locked counter backing merchants.services.next_public_id.

    Lives in the audit app because the custom admin config in core/apps.py
    means `core` is not a registered Django app and cannot own models.
    """

    prefix = models.CharField(max_length=12, primary_key=True)
    current = models.PositiveBigIntegerField(default=0)


class ApiCallLog(models.Model):
    """A scrubbed, per-attempt record of outbound provider traffic."""

    provider = models.CharField(max_length=100)
    method = models.CharField(max_length=10)
    endpoint = models.CharField(max_length=255)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    duration_ms = models.PositiveIntegerField(default=0)
    error_type = models.CharField(max_length=80, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "created_at"], name="audit_apica_provide_940e7c_idx"),
            models.Index(fields=["success", "created_at"], name="audit_apica_success_248774_idx"),
            models.Index(fields=["request_id"], name="audit_apica_request_d282dd_idx"),
        ]


class WebhookEvent(models.Model):
    """Durable log of inbound provider webhooks (eSign, DigiLocker).

    ``(provider, event_id)`` uniqueness is the dedupe key against provider
    redeliveries; rows are kept for reconciliation and replay forensics.
    """

    provider = models.CharField(max_length=20)
    event_id = models.CharField(max_length=80)
    event_type = models.CharField(max_length=80, blank=True)
    signature_valid = models.BooleanField(default=False)
    payload = models.JSONField(default=dict)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_result = models.CharField(max_length=40, default="received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "event_id"], name="unique_provider_event"),
        ]
