from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from catalog.models import Brand, ServiceType, VoucherProduct
from catalog.services import OrderPricingService
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
        code="BRANDED_VOUCHER",
        defaults={"name": "Branded Voucher", "is_active": True},
    )
    brand, _ = Brand.objects.get_or_create(
        slug="amazon",
        defaults={"name": "Amazon", "service_type": service},
    )
    product, _ = VoucherProduct.objects.get_or_create(
        brand=brand,
        denomination=Decimal("1000.00"),
        defaults={"name": "Amazon ₹1,000", "fee_rate": Decimal("0.02"), "tax_rate": Decimal("0.18")},
    )
    return product


@pytest.mark.django_db
class TestPaymentOrderRules:
    def test_merchant_cannot_order_before_activation(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        product = _product()
        with pytest.raises(ValidationError):
            PaymentOrderService.create(
                merchant=application.merchant,
                actor=merchant_user,
                product=product,
                quantity=10,
            )

    def test_server_recalculates_totals(self, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        quote = OrderPricingService.quote(product, quantity=100)
        assert quote.subtotal == Decimal("100000.00")
        assert quote.fees == Decimal("2000.00")
        assert quote.tax == Decimal("360.00")
        assert quote.total == Decimal("102360.00")
        order = PaymentOrderService.create(
            merchant=merchant,
            actor=merchant_user,
            product=product,
            quantity=100,
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        order.refresh_from_db()
        assert order.total == quote.total
        assert order.status == OrderStatus.SUBMITTED

    def test_employee_cannot_approve_own_submission(self, operations_user, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=merchant,
            actor=merchant_user,
            product=product,
            quantity=2,
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        order.submitted_by = operations_user
        order.save(update_fields=["submitted_by"])
        with pytest.raises(PermissionDenied):
            PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)

    def test_invalid_transition_is_rejected(self, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=merchant,
            actor=merchant_user,
            product=product,
            quantity=2,
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        with pytest.raises(ValidationError):
            PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)
