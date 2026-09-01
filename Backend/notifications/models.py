from django.conf import settings
from django.db import models


class DeliveryStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"
    BOUNCED = "BOUNCED", "Bounced"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=160)
    body = models.TextField()
    url = models.CharField(max_length=255, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "read_at"]),
        ]


class NotificationPreference(models.Model):
    """Per-user channel opt-ins.

    Security-relevant templates (verification codes, login alerts, session
    revocations, password resets) bypass preferences — see
    ``notifications.services.ALWAYS_ON_TEMPLATES``.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preference"
    )
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"NotificationPreference({self.user_id})"


class InboxThread(models.Model):
    subject = models.CharField(max_length=160)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="started_threads"
    )
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="inbox_threads")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class InboxMessage(models.Model):
    thread = models.ForeignKey(InboxThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class EmailLog(models.Model):
    public_id = models.CharField(max_length=32, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="email_logs",
    )
    recipient = models.EmailField(db_index=True)
    subject = models.CharField(max_length=200, blank=True)
    body_hash = models.CharField(max_length=64, blank=True)
    template_key = models.CharField(max_length=64, db_index=True)
    provider = models.CharField(max_length=32, default="ses")
    provider_message_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=16, choices=DeliveryStatus.choices, default=DeliveryStatus.QUEUED, db_index=True
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=128, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["recipient", "status"])]
        constraints = [
            models.UniqueConstraint(fields=["provider", "idempotency_key"], name="email_log_idem"),
        ]


class SmsLog(models.Model):
    public_id = models.CharField(max_length=32, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sms_logs",
    )
    recipient = models.CharField(max_length=20, db_index=True)
    body_preview = models.CharField(max_length=160, blank=True)
    body_hash = models.CharField(max_length=64, blank=True)
    template_key = models.CharField(max_length=64, db_index=True)
    provider = models.CharField(max_length=32, default="kaleyra")
    provider_message_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=16, choices=DeliveryStatus.choices, default=DeliveryStatus.QUEUED, db_index=True
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=128, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["recipient", "status"])]
        constraints = [
            models.UniqueConstraint(fields=["provider", "idempotency_key"], name="sms_log_idem"),
        ]
