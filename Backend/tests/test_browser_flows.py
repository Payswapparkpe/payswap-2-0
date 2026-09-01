import pytest


@pytest.mark.django_db
class TestBrowserFlows:
    """HTTP-level coverage of the three persona journeys used for release QA."""

    def test_admin_login_dashboard_and_cross_portal(self, client, admin_user):
        assert client.get("/login/").status_code == 200
        client.force_login(admin_user)
        dashboard = client.get("/administration/")
        assert dashboard.status_code == 200
        assert b"Needs attention" in dashboard.content
        assert client.get("/merchant/").status_code == 403
        assert client.get("/employee/").status_code == 403

    def test_employee_queue_not_admin(self, client, kyc_user):
        client.force_login(kyc_user)
        assert client.get("/employee/").status_code == 200
        assert b"My queue" in client.get("/employee/").content
        assert client.get("/administration/").status_code == 403

    def test_merchant_onboarding_pages(self, client, merchant_user):
        client.force_login(merchant_user)
        home = client.get("/merchant/")
        assert home.status_code == 200
        start = client.get("/merchant/onboarding/")
        assert start.status_code == 200
        create = client.get("/merchant/orders/new/")
        assert create.status_code == 200
        assert b"Step" in create.content
