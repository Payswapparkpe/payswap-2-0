import pytest
from django.test import Client, override_settings

from accounts.services import MfaService


@pytest.mark.django_db
class TestUnfoldAdminAccess:
    def test_login_page_uses_unfold(self, client):
        response = client.get("/admin/login/")
        assert response.status_code == 200
        html = response.content.decode()
        assert "unfold" in html
        assert "Payswap" in html

    def test_merchant_staff_cannot_use_admin(self, client, merchant_user):
        merchant_user.is_staff = True
        merchant_user.save(update_fields=["is_staff"])
        client.force_login(merchant_user)
        response = client.get("/admin/")
        assert response.status_code == 302
        assert "/admin/login/" in response["Location"]

    def test_admin_user_can_open_unfold(self, client, admin_user):
        client.force_login(admin_user)
        response = client.get("/admin/")
        assert response.status_code == 200
        assert "unfold" in response.content.decode()

    def test_production_ip_allowlist_blocks_unknown_clients(self, admin_user):
        client = Client(REMOTE_ADDR="203.0.113.10")
        client.force_login(admin_user)
        with override_settings(
            IS_PRODUCTION=True,
            ADMIN_ALLOWED_IPS=["10.8.0.0/24"],
            ADMIN_TRUST_X_FORWARDED_FOR=False,
            ADMIN_REQUIRE_OTP=False,
        ):
            blocked = client.get("/admin/")
            assert blocked.status_code == 403

        allowed = Client(REMOTE_ADDR="10.8.0.12")
        allowed.force_login(admin_user)
        with override_settings(
            IS_PRODUCTION=True,
            ADMIN_ALLOWED_IPS=["10.8.0.0/24"],
            ADMIN_TRUST_X_FORWARDED_FOR=False,
            ADMIN_REQUIRE_OTP=False,
        ):
            ok = allowed.get("/admin/")
            assert ok.status_code == 200

    def test_production_otp_required_without_verified_device(self, client, admin_user):
        client.force_login(admin_user)
        with override_settings(ADMIN_REQUIRE_OTP=True):
            response = client.get("/admin/")
            assert response.status_code == 302
            assert "/admin/login/" in response["Location"]

    def test_forwarded_for_is_used_when_trusted(self, admin_user):
        client = Client(
            REMOTE_ADDR="10.0.0.1",
            HTTP_X_FORWARDED_FOR="198.51.100.20, 10.0.0.1",
        )
        client.force_login(admin_user)
        with override_settings(
            IS_PRODUCTION=True,
            ADMIN_ALLOWED_IPS=["198.51.100.20"],
            ADMIN_TRUST_X_FORWARDED_FOR=True,
            ADMIN_REQUIRE_OTP=False,
        ):
            assert client.get("/admin/").status_code == 200


@pytest.mark.django_db
class TestAdminOtpLogin:
    def test_login_form_includes_authenticator_field(self, client):
        html = client.get("/admin/login/").content.decode()
        assert "otp_token" in html or "Authenticator" in html

    def test_mfa_enrolment_still_works_for_staff(self, admin_user):
        device, secret = MfaService.enrol(admin_user)
        assert secret
        assert device.user_id == admin_user.id


@pytest.mark.django_db
class TestOptionalAdminControls:
    def test_empty_ip_allowlist_means_no_restriction_in_production(self, admin_user):
        client = Client(REMOTE_ADDR="203.0.113.10")
        client.force_login(admin_user)
        with override_settings(
            IS_PRODUCTION=True,
            ADMIN_ALLOWED_IPS=[],
            ADMIN_REQUIRE_OTP=False,
        ):
            assert client.get("/admin/").status_code == 200

    def test_admin_not_forced_into_mfa_setup_when_otp_not_required(self, client, admin_user):
        assert not admin_user.mfa_enforced
        with override_settings(ADMIN_REQUIRE_OTP=False):
            response = client.post("/login/", {"email": admin_user.email, "password": "CorrectHorse9!"})
        assert response.status_code == 302
        assert response["Location"] == "/administration/"

    def test_admin_forced_into_mfa_setup_when_otp_required(self, client, admin_user):
        assert not admin_user.mfa_enforced
        with override_settings(ADMIN_REQUIRE_OTP=True):
            response = client.post("/login/", {"email": admin_user.email, "password": "CorrectHorse9!"})
        assert response.status_code == 302
        assert response["Location"] == "/mfa/setup/"

    def test_non_admin_never_forced_into_mfa_setup(self, client, merchant_user):
        with override_settings(ADMIN_REQUIRE_OTP=True):
            response = client.post("/login/", {"email": merchant_user.email, "password": "CorrectHorse9!"})
        assert response.status_code == 302
        assert response["Location"] == "/merchant/"

    def test_administration_portal_gated_until_mfa_enrolled(self, client, admin_user):
        assert not admin_user.mfa_enforced
        client.force_login(admin_user)
        with override_settings(ADMIN_REQUIRE_OTP=True):
            response = client.get("/administration/")
            assert response.status_code == 302
            assert response["Location"] == "/mfa/setup/"
        with override_settings(ADMIN_REQUIRE_OTP=False):
            assert client.get("/administration/").status_code == 200
