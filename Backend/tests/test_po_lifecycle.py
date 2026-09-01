from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from catalog.models import Brand, ServiceType, VoucherProduct
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService
from orders.models import ApprovalDecision, OrderStatus, PaymentOrder
from orders.services import PaymentOrderService
from tests.support import complete_required_draft


def _activated_merchant(merchant_user, admin_user):
    application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
    complete_required_draft(application)
    MerchantOnboardingService.submit(application, actor=merchant_user)
    MerchantOnboardingService.start_review(application, actor=admin_user)
    MerchantOnboardingService.approve(application, actor=admin_user)
    merchant = application.merchant
    merchant.commercial_status = Merchant.CommercialStatus.ACTIVE
    merchant.agreement_status = Merchant.VerificationState.VERIFIED
    merchant.save(update_fields=["commercial_status", "agreement_status"])
    return merchant


def _product():
    service, _ = ServiceType.objects.get_or_create(
        code="BRANDED_VOUCHER", defaults={"name": "Branded Voucher", "is_active": True}
    )
    brand, _ = Brand.objects.get_or_create(
        slug="amazon", defaults={"name": "Amazon", "service_type": service}
    )
    product, _ = VoucherProduct.objects.get_or_create(
        brand=brand,
        denomination=Decimal("1000.00"),
        defaults={"name": "Amazon ₹1,000", "fee_rate": Decimal("0.02"), "tax_rate": Decimal("0.18")},
    )
    return product


def _submitted_order(merchant, merchant_user, product):
    order = PaymentOrderService.create(merchant=merchant, actor=merchant_user, product=product, quantity=2)
    PaymentOrderService.submit(order, actor=merchant_user)
    order.refresh_from_db()
    return order


@pytest.mark.django_db
class TestPurchaseOrderLifecycle:
    def test_create_is_draft_until_submit(self, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=_product(), quantity=2
        )
        assert order.status == OrderStatus.DRAFT
        assert order.revisions.count() == 1
        PaymentOrderService.submit(order, actor=merchant_user)
        order.refresh_from_db()
        assert order.status == OrderStatus.SUBMITTED

    def test_create_is_idempotent_by_key(self, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        first = PaymentOrderService.create(
            merchant=merchant,
            actor=merchant_user,
            product=product,
            quantity=2,
            idempotency_key="merchant-1-cart-1",
        )
        second = PaymentOrderService.create(
            merchant=merchant,
            actor=merchant_user,
            product=product,
            quantity=5,
            idempotency_key="merchant-1-cart-1",
        )
        assert first.pk == second.pk
        assert PaymentOrder.objects.filter(merchant=merchant).count() == 1

    def test_draft_can_be_edited(self, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=product, quantity=2
        )
        PaymentOrderService.edit_draft(order=order, actor=merchant_user, product=product, quantity=7)
        order.refresh_from_db()
        assert order.quantity == 7
        assert order.revisions.get(revision=1).quantity == 7

    def test_submitted_order_cannot_be_edited(self, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = _submitted_order(merchant, merchant_user, product)
        with pytest.raises(ValidationError):
            PaymentOrderService.edit_draft(order=order, actor=merchant_user, product=product, quantity=9)

    def test_request_changes_and_resubmit(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = _submitted_order(merchant, merchant_user, _product())
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        PaymentOrderService.transition(
            order, OrderStatus.CHANGES_REQUESTED, actor=operations_user, reason="Quantity looks wrong"
        )
        order.refresh_from_db()
        assert order.status == OrderStatus.CHANGES_REQUESTED
        decision = order.decisions.get(action=ApprovalDecision.Action.REQUEST_CHANGES)
        assert decision.reason == "Quantity looks wrong"
        # Merchant edits the same revision and resubmits.
        PaymentOrderService.edit_draft(order=order, actor=merchant_user, product=order.product, quantity=3)
        PaymentOrderService.submit(order, actor=merchant_user)
        order.refresh_from_db()
        assert order.status == OrderStatus.SUBMITTED
        assert order.quantity == 3

    def test_reject_requires_reason(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = _submitted_order(merchant, merchant_user, _product())
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        with pytest.raises(ValidationError):
            PaymentOrderService.transition(order, OrderStatus.REJECTED, actor=operations_user, reason="")

    def test_rejected_order_is_terminal(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = _submitted_order(merchant, merchant_user, _product())
        PaymentOrderService.transition(
            order, OrderStatus.REJECTED, actor=operations_user, reason="Not eligible"
        )
        with pytest.raises(ValidationError):
            PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)

    def test_merchant_can_cancel_own_submitted_order(self, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = _submitted_order(merchant, merchant_user, _product())
        PaymentOrderService.cancel(order, actor=merchant_user, reason="Ordered by mistake")
        order.refresh_from_db()
        assert order.status == OrderStatus.CANCELLED

    def test_merchant_cannot_cancel_after_review_started(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = _submitted_order(merchant, merchant_user, _product())
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        with pytest.raises(ValidationError):
            PaymentOrderService.cancel(order, actor=merchant_user)

    def test_other_merchant_cannot_cancel(self, merchant_user, other_merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = _submitted_order(merchant, merchant_user, _product())
        with pytest.raises(PermissionDenied):
            PaymentOrderService.cancel(order, actor=other_merchant_user)

    def test_approval_is_pinned_to_revision(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = _submitted_order(merchant, merchant_user, _product())
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)
        decision = order.decisions.get(action=ApprovalDecision.Action.APPROVE)
        assert decision.revision.revision == 1

    def test_amend_creates_new_revision_and_requires_reapproval(
        self, merchant_user, admin_user, operations_user
    ):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = _submitted_order(merchant, merchant_user, product)
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)
        PaymentOrderService.amend(order=order, actor=operations_user, product=product, quantity=10)
        order.refresh_from_db()
        assert order.revision == 2
        assert order.status == OrderStatus.UNDER_REVIEW
        assert order.revisions.count() == 2
        # The original approval stays pinned to revision 1.
        assert order.decisions.get(action=ApprovalDecision.Action.APPROVE).revision.revision == 1

    def test_amend_blocked_once_rejected(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = _submitted_order(merchant, merchant_user, product)
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        PaymentOrderService.transition(
            order, OrderStatus.REJECTED, actor=operations_user, reason="Not eligible"
        )
        with pytest.raises(ValidationError):
            PaymentOrderService.amend(order=order, actor=operations_user, product=product, quantity=10)

    def test_review_requires_review_permission(self, merchant_user, admin_user, kyc_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = _submitted_order(merchant, merchant_user, _product())
        with pytest.raises(PermissionDenied):
            PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=kyc_user)

    def test_maker_cannot_approve_own_order(self, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = _submitted_order(merchant, merchant_user, _product())
        # Give the merchant owner staff-like rights to prove the maker/checker
        # rule is independent of permissions.
        from access.policy import Policy

        Policy.grant_role(merchant_user, "operations")
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=merchant_user)
        with pytest.raises(PermissionDenied):
            PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=merchant_user)
