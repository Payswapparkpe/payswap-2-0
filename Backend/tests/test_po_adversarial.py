"""Adversarial verification of the PO lifecycle.

These tests attempt the transitions and manipulations an attacker or a bug
would attempt, and assert the system blocks them. They complement the happy-path
lifecycle tests by proving the negative cases.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from catalog.models import Brand, ServiceType, VoucherProduct
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService
from orders.models import OrderStatus
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


def _to_approved(merchant, merchant_user, operations_user, product):
    order = PaymentOrderService.create(merchant=merchant, actor=merchant_user, product=product, quantity=2)
    PaymentOrderService.submit(order, actor=merchant_user)
    PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
    PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)
    order.refresh_from_db()
    return order


@pytest.mark.django_db
class TestInvalidTransitionsBlocked:
    def test_draft_cannot_jump_to_approved(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=_product(), quantity=1
        )
        with pytest.raises(ValidationError):
            PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)

    def test_rejected_cannot_be_approved(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=_product(), quantity=1
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        PaymentOrderService.transition(order, OrderStatus.REJECTED, actor=operations_user, reason="No")
        order.refresh_from_db()
        with pytest.raises(ValidationError):
            PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)

    def test_cancelled_cannot_be_approved(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=_product(), quantity=1
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        PaymentOrderService.cancel(order, actor=merchant_user, reason="mistake")
        order.refresh_from_db()
        with pytest.raises(ValidationError):
            PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)

    def test_approved_cannot_return_to_draft(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = _to_approved(merchant, merchant_user, operations_user, product)
        with pytest.raises(ValidationError):
            PaymentOrderService.transition(order, OrderStatus.DRAFT, actor=operations_user)

    def test_approved_order_cannot_be_silently_edited(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = _to_approved(merchant, merchant_user, operations_user, product)
        original_total = order.total
        with pytest.raises(ValidationError):
            PaymentOrderService.edit_draft(order=order, actor=merchant_user, product=product, quantity=99)
        order.refresh_from_db()
        assert order.total == original_total


@pytest.mark.django_db
class TestFinancialIntegrity:
    def test_server_recomputes_totals_not_client(self, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=product, quantity=100
        )
        quote_total = order.total
        # Client cannot influence total: it is derived from product + quantity.
        assert quote_total == Decimal("102360.00")
        # Check constraint: total must equal subtotal + fees + tax.
        order.refresh_from_db()
        assert order.total == order.subtotal + order.fees + order.tax
