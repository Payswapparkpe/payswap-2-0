import pytest
from django.urls import reverse

from merchants.services import MerchantOnboardingService


@pytest.mark.django_db
class TestPortalAccess:
    def test_anonymous_is_sent_to_login(self, client):
        response = client.get("/administration/")
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_merchant_cannot_open_admin_dashboard(self, client, merchant_user):
        client.force_login(merchant_user)
        response = client.get("/administration/")
        assert response.status_code == 403

    def test_employee_cannot_open_merchant_dashboard(self, client, kyc_user):
        client.force_login(kyc_user)
        response = client.get("/merchant/")
        assert response.status_code == 403

    def test_admin_dashboard_renders_empty_state(self, client, admin_user):
        client.force_login(admin_user)
        response = client.get("/administration/")
        assert response.status_code == 200
        assert b"Needs attention" in response.content
        assert b"12,450" not in response.content

    def test_merchant_cannot_open_another_application(self, client, merchant_user, other_merchant_user):
        application = MerchantOnboardingService.start(other_merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)
        url = reverse("merchant:onboarding_detail", kwargs={"public_id": application.public_id})
        response = client.get(url)
        assert response.status_code == 403
