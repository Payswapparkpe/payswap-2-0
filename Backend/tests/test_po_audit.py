from decimal import Decimal

import pytest

from audit.models import AuditEvent
from catalog.models import Brand, ServiceType, VoucherProduct
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService
from orders.models import ApprovalDecision, OrderStatus
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


@pytest.mark.django_db
class TestPurchaseOrderAudit:
    def test_full_lifecycle_writes_audit_and_decisions(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=product, quantity=2
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        PaymentOrderService.transition(
            order, OrderStatus.CHANGES_REQUESTED, actor=operations_user, reason="Fix quantity"
        )
        PaymentOrderService.edit_draft(order=order, actor=merchant_user, product=product, quantity=3)
        PaymentOrderService.submit(order, actor=merchant_user)
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)

        actions = set(
            AuditEvent.objects.filter(resource_type="order", resource_id=order.public_id).values_list(
                "action", flat=True
            )
        )
        assert {
            "order.create",
            "order.update",
            "order.submitted",
            "order.under_review",
            "order.changes_requested",
            "order.approved",
        } <= actions

        decisions = list(order.decisions.values_list("action", flat=True))
        assert ApprovalDecision.Action.REVIEW in decisions
        assert ApprovalDecision.Action.REQUEST_CHANGES in decisions
        assert ApprovalDecision.Action.APPROVE in decisions

        # Every decision is pinned to a revision and carries the reason.
        for decision in order.decisions.all():
            assert decision.revision.order_id == order.id
        assert order.decisions.get(action=ApprovalDecision.Action.REQUEST_CHANGES).reason == "Fix quantity"

    def test_events_carry_reason_and_revision(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=_product(), quantity=2
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        PaymentOrderService.transition(
            order, OrderStatus.REJECTED, actor=operations_user, reason="Duplicate order"
        )
        event = order.events.get(to_status=OrderStatus.REJECTED)
        assert event.reason == "Duplicate order"
        assert event.revision == order.revision

    def test_audit_does_not_store_secrets(self, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=_product(), quantity=2
        )
        for event in AuditEvent.objects.filter(resource_type="order", resource_id=order.public_id):
            blob = f"{event.before}{event.after}"
            assert "password" not in blob.lower()
            assert "otp" not in blob.lower()
