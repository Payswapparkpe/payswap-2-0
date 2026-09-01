import pytest
from django.test import override_settings

from notifications.sms_service import SmsService, _truncate_words


@pytest.mark.django_db
class TestSmsCompliance:
    def test_word_boundary_truncation(self):
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
        clipped = _truncate_words(text, 24)
        assert len(clipped) <= 24
        assert clipped.endswith("...")
        assert " " not in clipped.replace("...", "")[-1:] or clipped.count(" ") >= 1
        assert not clipped.startswith("...")

    def test_non_otp_appends_grievance_address(self, merchant_user):
        with override_settings(GRIEVANCE_POSTAL_ADDRESS="Mumbai HQ"):
            body = SmsService.render(
                "order_submitted",
                {"user": merchant_user, "title": "Submitted", "body": "OK", "reference": "ORD-1"},
            )
        assert "Mumbai HQ" in body
        assert len(body) <= 160

    def test_otp_does_not_append_address(self, merchant_user):
        with override_settings(GRIEVANCE_POSTAL_ADDRESS="Mumbai HQ"):
            body = SmsService.render("verification_code", {"user": merchant_user, "code": "654321"})
        assert "Mumbai HQ" not in body
        assert "654321" in body
