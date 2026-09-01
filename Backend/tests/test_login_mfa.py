import pytest

from accounts.services import MfaService


@pytest.mark.django_db
class TestLoginMfaGate:
    def test_enforced_mfa_does_not_complete_login(self, client, admin_user):
        device, secret = MfaService.enrol(admin_user)
        token = MfaService.current_token(secret)
        assert MfaService.verify(admin_user, token)
        response = client.post(
            "/login/",
            {"email": admin_user.email, "password": "CorrectHorse9!"},
        )
        assert response.status_code == 302
        assert response.url == "/mfa/"
        follow = client.get("/administration/")
        assert follow.status_code == 302
        assert "/login/" in follow.url

    def test_mfa_challenge_completes_login(self, client, admin_user):
        device, secret = MfaService.enrol(admin_user)
        device.confirmed = True
        device.save(update_fields=["confirmed"])
        admin_user.mfa_enforced = True
        admin_user.save(update_fields=["mfa_enforced"])
        client.post("/login/", {"email": admin_user.email, "password": "CorrectHorse9!"})
        next_token = MfaService.current_token(secret)
        response = client.post("/mfa/", {"token": next_token})
        assert response.status_code == 302
        dashboard = client.get("/administration/")
        assert dashboard.status_code == 200
