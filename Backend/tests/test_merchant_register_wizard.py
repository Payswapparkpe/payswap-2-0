"""Merchant registration wizard: details, verify, preview with terms acceptance."""

import pytest
from django.core import mail
from django.urls import reverse

from accounts.models import User
from merchants.models import Merchant
from merchants.privacy import decrypt_step_data


def _details(**overrides):
    payload = {
        "step": "details",
        "action": "continue",
        "name": "Priya Sharma",
        "email": "priya.register@payswap.test",
        "mobile": "9876543210",
        "address": "12 MG Road, Bengaluru",
        "pincode": "560001",
        "entity_type": "INDIVIDUAL",
        "password": "CorrectHorse9!",
        "confirm_password": "CorrectHorse9!",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
class TestMerchantRegisterWizard:
    def test_get_shows_three_steps_without_pan_or_dob(self, client):
        html = client.get("/merchant/register/").content.decode()
        assert html.count("stepper-item") == 3
        assert 'name="pan"' not in html
        assert 'name="dob"' not in html
        assert 'name="entity_type"' in html
        for _value, label in Merchant.EntityType.choices:
            assert label in html
        assert 'value="INDIVIDUAL"' in html
        assert "selected" in html
        assert 'name="pincode"' in html
        assert 'name="address"' in html
        assert "Work email" in html
        assert "Full name" in html
        assert 'placeholder="Enter your full name"' in html
        assert 'placeholder="Enter your work email"' in html
        assert 'placeholder="Enter your mobile number"' in html
        assert 'placeholder="Enter your address"' in html
        assert 'placeholder="Enter PIN code"' in html
        assert 'placeholder="Enter a password"' in html
        assert 'placeholder="Re-enter your password"' in html
        assert "field-control-ico" in html
        assert 'href="#i-mail"' in html
        assert "Priya Sharma" not in html
        assert "All rights reserved" in html
        assert "Create account and email details" not in html

    def test_details_then_verify_preview_creates_user_and_emails(self, client, settings, access_seed):
        settings.AUTH_TEST_MODE = True
        settings.TEST_OTP = "123456"
        details = _details(entity_type="PRIVATE_LIMITED")
        response = client.post("/merchant/register/", details)
        assert response.status_code == 302
        assert "step=verify" in response["Location"]

        client.post(
            "/merchant/register/",
            {"step": "verify", "action": "confirm_email", "email_code": "123456"},
        )
        client.post(
            "/merchant/register/",
            {"step": "verify", "action": "confirm_mobile", "mobile_code": "123456"},
        )
        response = client.post("/merchant/register/", {"step": "verify", "action": "continue"})
        assert response.status_code == 302
        assert "step=preview" in response["Location"]
        html = client.get("/merchant/register/?step=preview").content.decode()
        assert "Priya Sharma" in html
        assert "12 MG Road, Bengaluru" in html
        assert "560001" in html
        assert "Private Limited Company" in html
        assert "The password you chose is not shown here" in html
        assert "accept_terms" in html
        assert "Terms and Conditions" in html
        assert "/legal/terms/" in html
        assert "/legal/privacy/" in html
        assert "I accept the" in html

        response = client.post(
            "/merchant/register/",
            {"step": "preview", "action": "finish", "accept_terms": "on"},
        )
        assert response.status_code == 302
        assert response["Location"] == reverse("login") or response["Location"] == "/login/"
        user = User.objects.get(email="priya.register@payswap.test")
        assert user.email_verified_at
        assert user.mobile_verified_at
        assert user.check_password("CorrectHorse9!")
        assert not client.session.get("_auth_user_id")
        assert mail.outbox
        welcome = mail.outbox[-1]
        assert "priya.register@payswap.test" in welcome.body
        assert "CorrectHorse9!" not in welcome.body
        application = user.merchant.applications.first()
        assert user.merchant.entity_type == "PRIVATE_LIMITED"
        business = decrypt_step_data(application.steps.get(key="business").data)
        assert not business.get("pan")
        assert business.get("registered_office") == "12 MG Road, Bengaluru"
        assert business.get("pincode") == "560001"

    def test_verify_step_uses_otp_boxes_and_rejects_short_code(self, client, settings, access_seed):
        settings.AUTH_TEST_MODE = True
        settings.TEST_OTP = "123456"
        client.post(
            "/merchant/register/",
            _details(name="Otp Check", email="otp.check@payswap.test", mobile="9876543212"),
        )
        html = client.get("/merchant/register/?step=verify").content.decode()
        assert "otp-boxes" in html
        assert html.count("otp-digit") == 12
        assert "Email OTP" in html
        assert "Mobile OTP" in html
        assert ">Send</button>" not in html
        assert "Verify" in html
        assert "Resend" in html
        assert "data-otp-countdown" in html
        assert mail.outbox
        assert any("verification" in message.subject.lower() for message in mail.outbox)
        blocked = client.post(
            "/merchant/register/",
            {"step": "verify", "action": "send_email_otp"},
        )
        assert blocked.status_code == 400
        assert b"Wait" in blocked.content
        response = client.post(
            "/merchant/register/",
            {"step": "verify", "action": "confirm_email", "email_code": "12"},
        )
        assert response.status_code == 400
        assert b"valid OTP" in response.content

    def test_finish_without_terms_is_rejected(self, client, settings, access_seed):
        settings.AUTH_TEST_MODE = True
        settings.TEST_OTP = "123456"
        client.post(
            "/merchant/register/",
            _details(name="Terms Check", email="terms.check@payswap.test", mobile="9876543211"),
        )
        client.post(
            "/merchant/register/",
            {"step": "verify", "action": "confirm_email", "email_code": "123456"},
        )
        client.post(
            "/merchant/register/",
            {"step": "verify", "action": "confirm_mobile", "mobile_code": "123456"},
        )
        client.post("/merchant/register/", {"step": "verify", "action": "continue"})
        response = client.post("/merchant/register/", {"step": "preview", "action": "finish"})
        assert response.status_code == 400
        assert b"Accept the Terms and Conditions" in response.content
        assert not User.objects.filter(email="terms.check@payswap.test").exists()
