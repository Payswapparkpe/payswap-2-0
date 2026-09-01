from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from access.policy import Policy
from audit.services import AuditService
from catalog.services import OrderPricingService
from merchants.models import Merchant
from merchants.services import next_public_id
from notifications.services import NotificationService

from .models import (
    ApprovalDecision,
    OrderEvent,
    OrderRevision,
    OrderStatus,
    PaymentOrder,
)

# Actions that move an order through the staff review pipeline and therefore
# require both a permission and a persisted ApprovalDecision.
_REVIEW_PERMISSION = {
    OrderStatus.UNDER_REVIEW: "order.review",
    OrderStatus.APPROVED: "order.approve",
    OrderStatus.REJECTED: "order.reject",
    OrderStatus.CHANGES_REQUESTED: "order.request_changes",
}

_REVIEW_ACTION = {
    OrderStatus.UNDER_REVIEW: ApprovalDecision.Action.REVIEW,
    OrderStatus.APPROVED: ApprovalDecision.Action.APPROVE,
    OrderStatus.REJECTED: ApprovalDecision.Action.REJECT,
    OrderStatus.CHANGES_REQUESTED: ApprovalDecision.Action.REQUEST_CHANGES,
}


class PaymentOrderService:
    @staticmethod
    @transaction.atomic
    def create(
        *, merchant, actor, product, quantity: int, idempotency_key: str | None = None
    ) -> PaymentOrder:
        Policy.require(actor, "order.create", merchant)
        if merchant.owner_id != actor.id:
            raise PermissionDenied("You can only create orders for your own business.")
        if merchant.commercial_status != Merchant.CommercialStatus.ACTIVE:
            raise ValidationError("Your account must be approved before you can place orders.")
        if merchant.agreement_status != Merchant.VerificationState.VERIFIED:
            raise ValidationError("An executed agreement is required before you can place orders.")
        if idempotency_key:
            existing = PaymentOrder.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing
        quote = OrderPricingService.quote(product, quantity)
        order = PaymentOrder.objects.create(
            merchant=merchant,
            public_id=next_public_id("ORD", PaymentOrder),
            status=OrderStatus.DRAFT,
            product=product,
            quantity=quantity,
            unit_value=quote.unit_value,
            subtotal=quote.subtotal,
            fees=quote.fees,
            tax=quote.tax,
            total=quote.total,
            submitted_by=actor,
            idempotency_key=idempotency_key or None,
        )
        OrderRevision.objects.create(
            order=order,
            revision=1,
            product=product,
            quantity=quantity,
            unit_value=quote.unit_value,
            subtotal=quote.subtotal,
            fees=quote.fees,
            tax=quote.tax,
            total=quote.total,
            created_by=actor,
        )
        OrderEvent.objects.create(
            order=order, from_status="", to_status=OrderStatus.DRAFT, actor=actor, revision=1
        )
        AuditService.record(
            actor=actor,
            action="order.create",
            resource_type="order",
            resource_id=order.public_id,
            after={"total": str(order.total), "revision": 1},
        )
        return order

    @staticmethod
    @transaction.atomic
    def edit_draft(*, order: PaymentOrder, actor, product, quantity: int, request=None) -> PaymentOrder:
        """Edit content while the order is still merchant-editable.

        Content changes after submission are only possible via `amend`, which
        creates a new revision; this method refuses to touch frozen orders.
        """
        locked = PaymentOrder.objects.select_for_update().get(pk=order.pk)
        if locked.merchant.owner_id != actor.id:
            raise PermissionDenied("You can only edit your own orders.")
        if locked.status not in OrderStatus.MERCHANT_EDITABLE:
            raise ValidationError("This order can no longer be edited.")
        quote = OrderPricingService.quote(product, quantity)
        before = {"product_id": locked.product_id, "quantity": locked.quantity, "total": str(locked.total)}
        locked.product = product
        locked.quantity = quantity
        locked.unit_value = quote.unit_value
        locked.subtotal = quote.subtotal
        locked.fees = quote.fees
        locked.tax = quote.tax
        locked.total = quote.total
        locked.save(
            update_fields=[
                "product",
                "quantity",
                "unit_value",
                "subtotal",
                "fees",
                "tax",
                "total",
                "updated_at",
            ]
        )
        revision = locked.revisions.get(revision=locked.revision)
        revision.product = product
        revision.quantity = quantity
        revision.unit_value = quote.unit_value
        revision.subtotal = quote.subtotal
        revision.fees = quote.fees
        revision.tax = quote.tax
        revision.total = quote.total
        revision.save(update_fields=["product", "quantity", "unit_value", "subtotal", "fees", "tax", "total"])
        AuditService.record(
            actor=actor,
            action="order.update",
            resource_type="order",
            resource_id=locked.public_id,
            before=before,
            after={"product_id": product.id, "quantity": quantity, "total": str(quote.total)},
            request=request,
        )
        return locked

    @staticmethod
    @transaction.atomic
    def submit(order: PaymentOrder, *, actor, request=None) -> PaymentOrder:
        locked = PaymentOrder.objects.select_for_update().get(pk=order.pk)
        if locked.merchant.owner_id != actor.id:
            raise PermissionDenied("You can only submit your own orders.")
        return PaymentOrderService._transition(locked, OrderStatus.SUBMITTED, actor=actor, request=request)

    @staticmethod
    @transaction.atomic
    def cancel(order: PaymentOrder, *, actor, reason: str = "", request=None) -> PaymentOrder:
        Policy.require(actor, "order.cancel", order)
        locked = PaymentOrder.objects.select_for_update().get(pk=order.pk)
        is_owner = locked.merchant.owner_id == actor.id
        if is_owner and locked.status not in OrderStatus.MERCHANT_CANCELLABLE:
            raise ValidationError("This order can no longer be cancelled.")
        return PaymentOrderService._transition(
            locked, OrderStatus.CANCELLED, actor=actor, reason=reason, request=request
        )

    @staticmethod
    @transaction.atomic
    def amend(order: PaymentOrder, *, actor, product, quantity: int, request=None) -> PaymentOrder:
        """Create a new revision of an approved order.

        Amending returns the order to UNDER_REVIEW so the new content is
        re-approved against the new revision.
        """
        Policy.require(actor, "order.amend", order)
        locked = PaymentOrder.objects.select_for_update().get(pk=order.pk)
        if locked.status != OrderStatus.APPROVED:
            raise ValidationError("Only an approved order can be amended.")
        quote = OrderPricingService.quote(product, quantity)
        locked.revision += 1
        locked.product = product
        locked.quantity = quantity
        locked.unit_value = quote.unit_value
        locked.subtotal = quote.subtotal
        locked.fees = quote.fees
        locked.tax = quote.tax
        locked.total = quote.total
        locked.save(
            update_fields=[
                "revision",
                "product",
                "quantity",
                "unit_value",
                "subtotal",
                "fees",
                "tax",
                "total",
                "updated_at",
            ]
        )
        OrderRevision.objects.create(
            order=locked,
            revision=locked.revision,
            product=product,
            quantity=quantity,
            unit_value=quote.unit_value,
            subtotal=quote.subtotal,
            fees=quote.fees,
            tax=quote.tax,
            total=quote.total,
            created_by=actor,
        )
        AuditService.record(
            actor=actor,
            action="order.amend",
            resource_type="order",
            resource_id=locked.public_id,
            after={"revision": locked.revision, "total": str(quote.total)},
            request=request,
        )
        return PaymentOrderService._transition(
            locked,
            OrderStatus.UNDER_REVIEW,
            actor=actor,
            request=request,
            record_decision=False,
            check_permission=False,
        )

    @staticmethod
    @transaction.atomic
    def transition(
        order: PaymentOrder, to_state: str, *, actor, reason: str = "", request=None
    ) -> PaymentOrder:
        locked = PaymentOrder.objects.select_for_update().get(pk=order.pk)
        return PaymentOrderService._transition(locked, to_state, actor=actor, reason=reason, request=request)

    @staticmethod
    def _transition(
        order: PaymentOrder,
        to_state: str,
        *,
        actor,
        reason: str = "",
        request=None,
        record_decision: bool = True,
        check_permission: bool = True,
    ) -> PaymentOrder:
        """Move an order between states. The caller must hold the row lock.

        Review-pipeline transitions (review/approve/reject/request-changes)
        require their specific permission and persist an ApprovalDecision
        pinned to the current revision. A maker can never approve their own
        order (enforced in Policy._order_approve).
        """
        allowed = OrderStatus.TRANSITIONS.get(order.status, set())
        if to_state not in allowed:
            raise ValidationError(f"Order {order.public_id} cannot move from {order.status} to {to_state}.")
        permission = _REVIEW_PERMISSION.get(to_state)
        if permission is not None and check_permission:
            Policy.require(actor, permission, order)
            if to_state in {OrderStatus.REJECTED, OrderStatus.CHANGES_REQUESTED} and not reason.strip():
                raise ValidationError("A reason is required for this decision.")
        previous = order.status
        order.status = to_state
        order.save(update_fields=["status", "updated_at"])
        request_id = getattr(request, "request_id", "") if request is not None else ""
        if permission is not None and record_decision:
            ApprovalDecision.objects.create(
                order=order,
                revision=order.revisions.get(revision=order.revision),
                actor=actor,
                action=_REVIEW_ACTION[to_state],
                reason=reason.strip(),
                request_id=request_id,
            )
        OrderEvent.objects.create(
            order=order,
            from_status=previous,
            to_status=to_state,
            actor=actor,
            revision=order.revision,
            reason=reason.strip(),
            request_id=request_id,
        )
        AuditService.record(
            actor=actor,
            action=f"order.{to_state.lower()}",
            resource_type="order",
            resource_id=order.public_id,
            before={"status": previous},
            after={"status": to_state, "revision": order.revision},
            reason=reason.strip(),
            request=request,
        )
        PaymentOrderService._notify(order, to_state)
        return order

    @staticmethod
    def _notify(order: PaymentOrder, to_state: str) -> None:
        owner = order.merchant.owner
        url = f"/merchant/orders/{order.public_id}/"
        messages = {
            OrderStatus.SUBMITTED: (
                "Order submitted",
                f"Order {order.public_id} was submitted for review.",
                "order_submitted",
            ),
            OrderStatus.APPROVED: (
                "Order approved",
                f"Order {order.public_id} has been approved.",
                "order_approved",
            ),
            OrderStatus.REJECTED: (
                "Order rejected",
                f"Order {order.public_id} was rejected.",
                "order_rejected",
            ),
            OrderStatus.CHANGES_REQUESTED: (
                "Changes requested",
                f"Changes were requested on order {order.public_id}.",
                "order_changes_requested",
            ),
            OrderStatus.CANCELLED: (
                "Order cancelled",
                f"Order {order.public_id} has been cancelled.",
                "order_cancelled",
            ),
        }
        message = messages.get(to_state)
        if message is None:
            return
        title, body, template = message
        reason = ""
        decision = order.decisions.order_by("-created_at").first()
        if decision and getattr(decision, "reason", ""):
            reason = decision.reason
        product = getattr(order, "product", None)
        brand = getattr(product, "brand", None) if product else None
        NotificationService.notify(
            user=owner,
            title=title,
            body=body,
            url=url,
            email=True,
            template=template,
            context={
                "reference": order.public_id,
                "product_name": getattr(product, "name", ""),
                "brand_name": getattr(brand, "name", ""),
                "quantity": order.quantity,
                "total": str(order.total),
                "reason": reason,
            },
        )
