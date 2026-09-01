from datetime import timedelta

import pytest
from django.utils import timezone


@pytest.mark.django_db
class TestSessionIdleTimeout:
    def test_idle_session_is_logged_out(self, client, merchant_user, settings):
        settings.SESSION_IDLE_TIMEOUT_SECONDS = 60
        client.force_login(merchant_user)
        session = client.session
        session["idle_at"] = (timezone.now() - timedelta(minutes=5)).isoformat()
        session.save()
        response = client.get("/merchant/")
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_active_session_is_refreshed(self, client, merchant_user, settings):
        settings.SESSION_IDLE_TIMEOUT_SECONDS = 1800
        client.force_login(merchant_user)
        response = client.get("/merchant/")
        assert response.status_code == 200
        assert client.session.get("idle_at")
