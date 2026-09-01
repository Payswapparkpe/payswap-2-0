from django.conf import settings
from django.db import models
from django.db.models import Q


class OrderStatus:
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    CHOICES = [
        (DRAFT, "Draft"),
        (SUBMITTED, "Submitted"),
        (UNDER_REVIEW, "Under review"),
        (CHANGES_REQUESTED, "Changes requested"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (CANCELLED, "Cancelled"),
    ]

    # Editable by the merchant only while the order has not been accepted into
    # the review pipeline. Once under review the content is frozen; changes
    # after that require a new revision (amendment).
    MERCHANT_EDITABLE = {DRAFT, CHANGES_REQUESTED}
    # States in which the merchant may still cancel without staff involvement.
    MERCHANT_CANCELLABLE = {DRAFT, SUBMITTED, CHANGES_REQUESTED}

    TRANSITIONS = {
        DRAFT: {SUBMITTED, CANCELLED},
        SUBMITTED: {UNDER_REVIEW, REJECTED, CANCELLED},
        UNDER_REVIEW: {APPROVED, REJECTED, CHANGES_REQUESTED},
        CHANGES_REQUESTED: {SUBMITTED, CANCELLED},
        APPROVED: {UNDER_REVIEW, CANCELLED},
        REJECTED: set(),
        CANCELLED: set(),
    }


class PaymentOrder(models.Model):
    merchant = models.ForeignKey("merchants.Merchant", on_delete=models.PROTECT, related_name="orders")
    public_id = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=30, choices=OrderStatus.CHOICES, default=OrderStatus.DRAFT)
    product = models.ForeignKey("catalog.VoucherProduct", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_value = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    fees = models.DecimalField(max_digits=14, decimal_places=2)
    tax = models.DecimalField(max_digits=14, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    revision = models.PositiveIntegerField(default=1)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_orders"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_orders",
    )
    idempotency_key = models.CharField(max_length=64, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["merchant", "status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="order_quantity_positive"),
            models.CheckConstraint(condition=Q(subtotal__gte=0), name="order_subtotal_nonnegative"),
            models.CheckConstraint(condition=Q(fees__gte=0), name="order_fees_nonnegative"),
            models.CheckConstraint(condition=Q(tax__gte=0), name="order_tax_nonnegative"),
            models.CheckConstraint(condition=Q(total__gte=0), name="order_total_nonnegative"),
            models.CheckConstraint(
                condition=Q(total=models.F("subtotal") + models.F("fees") + models.F("tax")),
                name="order_total_matches_parts",
            ),
        ]


class OrderRevision(models.Model):
    """Immutable snapshot of an order's commercial content.

    Approval decisions reference a revision so a post-approval amendment can
    never silently change what was approved.
    """

    order = models.ForeignKey(PaymentOrder, on_delete=models.CASCADE, related_name="revisions")
    revision = models.PositiveIntegerField()
    product = models.ForeignKey("catalog.VoucherProduct", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_value = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    fees = models.DecimalField(max_digits=14, decimal_places=2)
    tax = models.DecimalField(max_digits=14, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-revision"]
        constraints = [
            models.UniqueConstraint(fields=["order", "revision"], name="unique_order_revision"),
        ]


class ApprovalDecision(models.Model):
    """Persisted record of a review decision against a specific revision."""

    class Action:
        REVIEW = "review"
        APPROVE = "approve"
        REJECT = "reject"
        REQUEST_CHANGES = "request_changes"

        CHOICES = [
            (REVIEW, "Review"),
            (APPROVE, "Approve"),
            (REJECT, "Reject"),
            (REQUEST_CHANGES, "Request changes"),
        ]

    order = models.ForeignKey(PaymentOrder, on_delete=models.CASCADE, related_name="decisions")
    revision = models.ForeignKey(OrderRevision, on_delete=models.PROTECT, related_name="decisions")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=20, choices=Action.CHOICES)
    reason = models.TextField(blank=True)
    level = models.PositiveIntegerField(default=1)
    request_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "created_at"]),
        ]


class OrderEvent(models.Model):
    order = models.ForeignKey(PaymentOrder, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    revision = models.PositiveIntegerField(null=True, blank=True)
    reason = models.TextField(blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_to_status_display(self) -> str:
        return dict(OrderStatus.CHOICES).get(self.to_status, self.to_status)
