from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    class UserType(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        EMPLOYEE = "EMPLOYEE", "Employee"
        MERCHANT = "MERCHANT", "Merchant"

    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=15, blank=True)
    name = models.CharField(max_length=150, blank=True)
    user_type = models.CharField(max_length=20, choices=UserType.choices)
    department = models.ForeignKey(
        "access.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    mobile_verified_at = models.DateTimeField(null=True, blank=True)
    mfa_enforced = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["user_type"]

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    @property
    def display_name(self):
        name = (self.name or "").strip()
        if name:
            return name
        local = (self.email or "").split("@")[0].replace(".", " ").replace("_", " ")
        return local.title() if local else "Account"

    @property
    def initials(self):
        parts = [part for part in (self.name or "").split() if part]
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[-1][0]}".upper()
        if parts:
            return parts[0][:2].upper()
        email = (self.email or "?").strip()
        return email[:1].upper()

    @property
    def is_admin_user(self):
        return self.user_type == self.UserType.ADMIN

    @property
    def is_employee_user(self):
        return self.user_type == self.UserType.EMPLOYEE

    @property
    def is_merchant_user(self):
        return self.user_type == self.UserType.MERCHANT


class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tracked_sessions")
    session_key = models.CharField(max_length=40, db_index=True)
    user_agent = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]


class VerificationChallenge(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        MOBILE = "mobile", "Mobile"
        STEP_UP = "step_up", "Step-up"

    class Purpose(models.TextChoices):
        VERIFICATION = "verification", "Contact verification"
        AUTHENTICATION = "authentication", "Login"
        SECURITY_ACTION = "security_action", "Security change"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="challenges")
    channel = models.CharField(max_length=20, choices=Channel.choices)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.VERIFICATION)
    destination_masked = models.CharField(max_length=60, blank=True)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    request_id = models.CharField(max_length=32, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "channel", "created_at"]),
            models.Index(fields=["user", "purpose", "created_at"]),
        ]


class SecurityCredential(models.Model):
    """MPIN state for an account. MPIN is stored as an Argon2id hash only."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="security_credential")
    mpin_hash = models.CharField(max_length=255, blank=True)
    mpin_enabled = models.BooleanField(default=False)
    mpin_created_at = models.DateTimeField(null=True, blank=True)
    mpin_changed_at = models.DateTimeField(null=True, blank=True)
    mpin_failed_attempts = models.PositiveSmallIntegerField(default=0)
    mpin_locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["user__email"]


class RecoveryCode(models.Model):
    """Single-use TOTP recovery code; stored as a keyed HMAC hash."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_codes")
    code_hash = models.CharField(max_length=64, unique=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "used_at"])]


class PasskeyCredential(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="passkeys")
    credential_id = models.CharField(max_length=128, unique=True)
    public_key_hex = models.CharField(max_length=128)
    sign_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class LoginEvent(models.Model):
    class Result(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"
        MFA_FAILURE = "mfa_failure", "MFA failure"

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    email = models.EmailField()
    result = models.CharField(max_length=20, choices=Result.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "result", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
        ]
