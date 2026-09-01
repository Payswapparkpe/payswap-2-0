import pytest


@pytest.mark.django_db
class TestPortalPages:
    def test_admin_roles_and_orders(self, client, admin_user):
        client.force_login(admin_user)
        assert client.get("/administration/roles/").status_code == 200
        assert client.get("/administration/orders/").status_code == 200

    def test_merchant_orders_and_profile(self, client, merchant_user):
        from merchants.services import MerchantOnboardingService

        MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)
        assert client.get("/merchant/orders/").status_code == 200
        assert client.get("/merchant/profile/").status_code == 200
        assert client.get("/merchant/documents/").status_code == 200

    def test_employee_cannot_open_admin_roles(self, client, kyc_user):
        client.force_login(kyc_user)
        assert client.get("/administration/roles/").status_code == 403
        assert client.get("/employee/orders/").status_code == 200
        assert client.get("/employee/queue/").status_code == 200
