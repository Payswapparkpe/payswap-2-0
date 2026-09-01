from django.conf import settings
from django.db import models

from core.crypto import decrypt_text, encrypt_text

from .states import ApplicationStatus, StepStatus


class Merchant(models.Model):
    class EntityType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        PROPRIETORSHIP = "PROPRIETORSHIP", "Proprietorship"
        PARTNERSHIP = "PARTNERSHIP", "Partnership"
        LLP = "LLP", "LLP"
        PRIVATE_LIMITED = "PRIVATE_LIMITED", "Private Limited Company"
        PUBLIC_LIMITED = "PUBLIC_LIMITED", "Public Limited Company"
        TRUST = "TRUST", "Trust"
        SOCIETY = "SOCIETY", "Society"
        HUF = "HUF", "HUF"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_REVIEW = "PENDING_REVIEW", "Pending review"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        REJECTED = "REJECTED", "Rejected"

    class VerificationState(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not started"
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        ACTION_REQUIRED = "ACTION_REQUIRED", "Action required"
        REJECTED = "REJECTED", "Rejected"

    class RiskStatus(models.TextChoices):
        CLEAR = "CLEAR", "Clear"
        REVIEW = "REVIEW", "Review"
        HIGH = "HIGH", "High"

    class CommercialStatus(models.TextChoices):
        INACTIVE = "INACTIVE", "Inactive"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"

    public_id = models.CharField(max_length=20, unique=True)
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="merchant")
    business_name = models.CharField(max_length=200, blank=True)
    entity_type = models.CharField(max_length=30, choices=EntityType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    kyc_status = models.CharField(
        max_length=20, choices=VerificationState.choices, default=VerificationState.NOT_STARTED
    )
    kyb_status = models.CharField(
        max_length=20, choices=VerificationState.choices, default=VerificationState.NOT_STARTED
    )
    bank_status = models.CharField(
        max_length=20, choices=VerificationState.choices, default=VerificationState.NOT_STARTED
    )
    agreement_status = models.CharField(
        max_length=20, choices=VerificationState.choices, default=VerificationState.NOT_STARTED
    )
    risk_status = models.CharField(max_length=20, choices=RiskStatus.choices, default=RiskStatus.CLEAR)
    commercial_status = models.CharField(
        max_length=20, choices=CommercialStatus.choices, default=CommercialStatus.INACTIVE
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_merchants",
    )
    assigned_department = models.ForeignKey(
        "access.Department", null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.business_name or self.public_id


class OnboardingApplication(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="applications")
    public_id = models.CharField(max_length=20, unique=True)
    status = models.CharField(
        max_length=30, choices=ApplicationStatus.CHOICES, default=ApplicationStatus.DRAFT
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_applications",
    )
    rejection_reason = models.CharField(max_length=80, blank=True)
    rejection_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["merchant", "created_at"]),
        ]


class OnboardingStep(models.Model):
    application = models.ForeignKey(OnboardingApplication, on_delete=models.CASCADE, related_name="steps")
    key = models.CharField(max_length=30)
    title = models.CharField(max_length=80)
    position = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=30, choices=StepStatus.CHOICES, default=StepStatus.NOT_STARTED)
    data = models.JSONField(default=dict, blank=True)
    clarification_message = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("application", "key")
        ordering = ["position"]


class BeneficialOwner(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="owners")
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=80, blank=True)
    ownership_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    pan_encrypted = models.TextField(blank=True)
    pan_last4 = models.CharField(max_length=4, blank=True)
    is_authorized_signatory = models.BooleanField(default=False)

    @property
    def pan(self) -> str:
        return decrypt_text(self.pan_encrypted) if self.pan_encrypted else ""

    def set_pan(self, value: str) -> None:
        if value:
            self.pan_encrypted = encrypt_text(value)
            self.pan_last4 = value[-4:]
        else:
            self.pan_encrypted = ""
            self.pan_last4 = ""
