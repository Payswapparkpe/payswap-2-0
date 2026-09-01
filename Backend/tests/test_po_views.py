from decimal import Decimal

import pytest

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


@pytest.mark.django_db
class TestMerchantOrderViews:
    def test_create_flow_submits_and_redirects(self, client, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        client.force_login(merchant_user)
        response = client.post(
            "/merchant/orders/new/",
            {"product": product.pk, "quantity": 3, "idempotency_key": "key-1"},
        )
        assert response.status_code == 302
        order = merchant.orders.get()
        assert response.url == f"/merchant/orders/{order.public_id}/"
        assert order.status == OrderStatus.SUBMITTED

    def test_create_flow_is_idempotent_on_resubmit(self, client, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        client.force_login(merchant_user)
        payload = {"product": product.pk, "quantity": 3, "idempotency_key": "key-2"}
        client.post("/merchant/orders/new/", payload)
        client.post("/merchant/orders/new/", payload)
        assert merchant.orders.count() == 1

    def test_merchant_edits_changes_requested_order(self, client, merchant_user, admin_user, operations_user):
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
        client.force_login(merchant_user)
        response = client.post(
            f"/merchant/orders/{order.public_id}/",
            {"action": "edit", "product": product.pk, "quantity": 5},
        )
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.quantity == 5
        response = client.post(f"/merchant/orders/{order.public_id}/", {"action": "submit"})
        order.refresh_from_db()
        assert order.status == OrderStatus.SUBMITTED

    def test_merchant_cancels_own_draft(self, client, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=product, quantity=2
        )
        client.force_login(merchant_user)
        response = client.post(f"/merchant/orders/{order.public_id}/", {"action": "cancel"})
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == OrderStatus.CANCELLED

    def test_other_merchant_cannot_see_order(self, client, merchant_user, other_merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=product, quantity=2
        )
        client.force_login(other_merchant_user)
        assert client.get(f"/merchant/orders/{order.public_id}/").status_code == 404
        assert client.post(f"/merchant/orders/{order.public_id}/", {"action": "cancel"}).status_code == 404


@pytest.mark.django_db
class TestEmployeeOrderViews:
    def test_approve_requires_review_first(self, client, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=product, quantity=2
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        client.force_login(operations_user)
        # Approving straight from SUBMITTED is no longer possible — review first.
        client.post(f"/employee/orders/{order.public_id}/", {"action": "approve"})
        order.refresh_from_db()
        assert order.status == OrderStatus.SUBMITTED
        client.post(f"/employee/orders/{order.public_id}/", {"action": "review"})
        client.post(f"/employee/orders/{order.public_id}/", {"action": "approve"})
        order.refresh_from_db()
        assert order.status == OrderStatus.APPROVED

    def test_reject_requires_reason(self, client, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=product, quantity=2
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        client.force_login(operations_user)
        client.post(f"/employee/orders/{order.public_id}/", {"action": "review"})
        client.post(f"/employee/orders/{order.public_id}/", {"action": "reject", "reason": ""})
        order.refresh_from_db()
        assert order.status == OrderStatus.UNDER_REVIEW
        client.post(f"/employee/orders/{order.public_id}/", {"action": "reject", "reason": "Not eligible"})
        order.refresh_from_db()
        assert order.status == OrderStatus.REJECTED

    def test_kyc_cannot_approve(self, client, merchant_user, admin_user, kyc_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=product, quantity=2
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        client.force_login(kyc_user)
        client.post(f"/employee/orders/{order.public_id}/", {"action": "review"})
        order.refresh_from_db()
        assert order.status == OrderStatus.SUBMITTED

    def test_order_page_shows_history(self, client, merchant_user, admin_user, operations_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=product, quantity=2
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        client.force_login(operations_user)
        response = client.get(f"/employee/orders/{order.public_id}/")
        assert response.status_code == 200
        assert b"History" in response.content
        assert b"SUBMITTED" in response.content
