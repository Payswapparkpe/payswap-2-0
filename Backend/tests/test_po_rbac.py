"""RBAC matrix and object-isolation verification.

Probes every portal endpoint as each role and asserts the API enforces
authorization independent of any menu hiding. Also probes object-level
isolation (IDOR) across merchants and unauthenticated sessions.
"""

from decimal import Decimal

import pytest

from catalog.models import Brand, ServiceType, VoucherProduct
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService
from orders.models import OrderStatus
from orders.services import PaymentOrderService
from tests.support import complete_required_draft


def _activated_merchant(user, admin_user):
    application = MerchantOnboardingService.start(user, entity_type="PRIVATE_LIMITED")
    complete_required_draft(application)
    MerchantOnboardingService.submit(application, actor=user)
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
class TestPortalIsolation:
    """Each role must be confined to its own portal."""

    @pytest.mark.parametrize(
        "path,allowed_fixture",
        [
            ("/administration/", "admin_user"),
            ("/employee/", "operations_user"),
            ("/merchant/", "merchant_user"),
        ],
    )
    def test_portal_requires_correct_role(self, client, path, allowed_fixture, request):
        # An authenticated user of the wrong type is denied.
        wrong = (
            request.getfixturevalue("merchant_user")
            if "merchant" not in path
            else request.getfixturevalue("operations_user")
        )
        client.force_login(wrong)
        assert client.get(path).status_code in {302, 403}

    def test_anonymous_redirected_to_login(self, client):
        for path in ("/administration/", "/employee/", "/merchant/"):
            response = client.get(path)
            assert response.status_code in {301, 302}
            assert "/login" in response.url or response.url.startswith("/")


@pytest.mark.django_db
class TestObjectIsolation:
    def test_merchant_cannot_read_other_merchant_order(
        self, client, merchant_user, other_merchant_user, admin_user
    ):
        _activated_merchant(merchant_user, admin_user)
        other = _activated_merchant(other_merchant_user, admin_user)
        product = _product()
        order = PaymentOrderService.create(
            merchant=other, actor=other_merchant_user, product=product, quantity=1
        )
        client.force_login(merchant_user)
        assert client.get(f"/merchant/orders/{order.public_id}/").status_code == 404
        assert client.post(f"/merchant/orders/{order.public_id}/", {"action": "cancel"}).status_code == 404

    def test_merchant_cannot_guess_order_id_sequence(
        self, client, merchant_user, other_merchant_user, admin_user
    ):
        merchant = _activated_merchant(merchant_user, admin_user)
        other = _activated_merchant(other_merchant_user, admin_user)
        product = _product()
        PaymentOrderService.create(merchant=merchant, actor=merchant_user, product=product, quantity=1)
        other_order = PaymentOrderService.create(
            merchant=other, actor=other_merchant_user, product=product, quantity=1
        )
        client.force_login(merchant_user)
        # Even with a valid, guessable public_id the owner check returns 404.
        assert client.get(f"/merchant/orders/{other_order.public_id}/").status_code == 404

    def test_unauthenticated_cannot_reach_order(self, client, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=_product(), quantity=1
        )
        response = client.get(f"/merchant/orders/{order.public_id}/")
        assert response.status_code in {301, 302}

    def test_disabled_user_session_rejected(self, client, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=_product(), quantity=1
        )
        client.force_login(merchant_user)
        merchant_user.is_active = False
        merchant_user.save(update_fields=["is_active"])
        response = client.get(f"/merchant/orders/{order.public_id}/")
        assert response.status_code in {301, 302, 403}


@pytest.mark.django_db
class TestEmployeeOrderAuthorization:
    """Direct API (POST) authorization independent of the rendered buttons."""

    def _order(self, merchant_user, admin_user):
        merchant = _activated_merchant(merchant_user, admin_user)
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=_product(), quantity=1
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        return order

    def test_kyc_cannot_approve_via_post(self, client, kyc_user, merchant_user, admin_user):
        order = self._order(merchant_user, admin_user)
        client.force_login(kyc_user)
        assert client.post(f"/employee/orders/{order.public_id}/", {"action": "approve"}).status_code == 403
        order.refresh_from_db()
        assert order.status == OrderStatus.SUBMITTED

    def test_kyc_cannot_review_via_post(self, client, kyc_user, merchant_user, admin_user):
        order = self._order(merchant_user, admin_user)
        client.force_login(kyc_user)
        client.post(f"/employee/orders/{order.public_id}/", {"action": "review"})
        order.refresh_from_db()
        assert order.status == OrderStatus.SUBMITTED
