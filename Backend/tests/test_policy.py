import pytest
from django.core.exceptions import PermissionDenied

from access.policy import Policy
from merchants.models import Merchant


@pytest.mark.django_db
class TestPortalIsolation:
    def test_admin_can_open_administration(self, admin_user):
        assert Policy.can(admin_user, "portal.administration")

    def test_admin_cannot_open_merchant_portal(self, admin_user):
        assert not Policy.can(admin_user, "portal.merchant")

    def test_employee_can_open_employee_portal(self, kyc_user):
        assert Policy.can(kyc_user, "portal.employee")

    def test_employee_cannot_open_administration(self, kyc_user):
        assert not Policy.can(kyc_user, "portal.administration")

    def test_merchant_cannot_open_employee_or_admin(self, merchant_user):
        assert Policy.can(merchant_user, "portal.merchant")
        assert not Policy.can(merchant_user, "portal.employee")
        assert not Policy.can(merchant_user, "portal.administration")

    def test_require_raises_on_denial(self, merchant_user):
        with pytest.raises(PermissionDenied):
            Policy.require(merchant_user, "portal.administration")


@pytest.mark.django_db
class TestPermissionMatrix:
    def test_kyc_can_approve_kyc_not_orders(self, kyc_user):
        assert Policy.can(kyc_user, "kyc.approve")
        assert not Policy.can(kyc_user, "order.approve")

    def test_operations_can_approve_order_not_kyc(self, operations_user):
        assert Policy.can(operations_user, "order.approve")
        assert not Policy.can(operations_user, "kyc.approve")

    def test_merchant_can_create_order_staff_cannot(self, merchant_user, kyc_user):
        assert Policy.can(merchant_user, "order.create")
        assert not Policy.can(kyc_user, "order.create")

    def test_merchant_cannot_view_another_merchant(self, merchant_user, other_merchant_user):
        own = Merchant.objects.create(
            public_id="PSM-000001",
            business_name="Own Co",
            entity_type="PRIVATE_LIMITED",
            owner=merchant_user,
        )
        other = Merchant.objects.create(
            public_id="PSM-000002",
            business_name="Other Co",
            entity_type="PRIVATE_LIMITED",
            owner=other_merchant_user,
        )
        assert Policy.can(merchant_user, "merchant.view", own)
        assert not Policy.can(merchant_user, "merchant.view", other)
        assert Policy.can(other_merchant_user, "merchant.view", other)
