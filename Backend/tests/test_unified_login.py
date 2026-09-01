import pytest


@pytest.mark.django_db
class TestUnifiedLogin:
    def test_old_portal_login_urls_redirect_to_shared_login(self, client):
        for path in ("/administration/login/", "/employee/login/", "/merchant/login/"):
            response = client.get(path)
            assert response.status_code == 302
            assert response.url.startswith("/login/")

    def test_admin_not_forced_to_authenticator_setup_in_development(self, client, admin_user):
        response = client.post("/login/", {"email": admin_user.email, "password": "CorrectHorse9!"})
        assert response.status_code == 302
        assert response.url == "/administration/"

    def test_employee_is_sent_to_mfa_when_role_requires_it(self, client, kyc_user):
        response = client.post("/login/", {"email": kyc_user.email, "password": "CorrectHorse9!"})
        assert response.status_code == 302
        assert response.url == "/mfa/"

    def test_merchant_lands_in_merchant_portal(self, client, merchant_user):
        response = client.post("/login/", {"email": merchant_user.email, "password": "CorrectHorse9!"})
        assert response.status_code == 302
        assert response.url == "/merchant/"

    def test_next_is_rejected_across_roles(self, client, merchant_user):
        response = client.post(
            "/login/",
            {
                "email": merchant_user.email,
                "password": "CorrectHorse9!",
                "next": "/administration/",
            },
        )
        assert response.status_code == 302
        assert response.url == "/merchant/"

    def test_safe_next_is_honoured_for_matching_role(self, client, merchant_user):
        response = client.post(
            "/login/",
            {
                "email": merchant_user.email,
                "password": "CorrectHorse9!",
                "next": "/merchant/orders/",
            },
        )
        assert response.status_code == 302
        assert response.url == "/merchant/orders/"

    def test_login_page_has_labels_and_brand(self, client):
        html = client.get("/login/").content.decode()
        assert "Email" in html
        assert "Password" in html
        assert 'placeholder="Enter your email"' in html
        assert 'placeholder="Enter your password"' in html
        assert "field-control-ico" in html
        assert 'href="#i-mail"' in html
        assert 'href="#i-lock"' in html
        assert "auth-card-brand" in html
        assert "images/logo/payswap.png" in html
        assert "Welcome back" in html
