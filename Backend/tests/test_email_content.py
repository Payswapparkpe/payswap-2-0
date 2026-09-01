import pytest
from django.core import mail
from django.test import override_settings

from notifications.email_service import EmailService
from notifications.models import Notification
from notifications.services import NotificationService


@pytest.mark.django_db
class TestEmailContent:
    def test_footer_includes_address_and_preferences(self, merchant_user):
        with override_settings(GRIEVANCE_POSTAL_ADDRESS="1 Example Road, Mumbai 400001"):
            EmailService.send(
                to=merchant_user.email,
                template="generic_notice",
                context={"user": merchant_user, "title": "Hello", "body": "World"},
            )
        body = mail.outbox[-1].body
        html = mail.outbox[-1].alternatives[0][0]
        assert "1 Example Road" in body
        assert "Notification preferences" in body or "preferences" in body.lower()
        assert "1 Example Road" in html
        assert "payswap.test" in body or merchant_user.email in body

    def test_welcome_uses_email_fallback(self):
        html, text, subject = EmailService.render(
            "welcome",
            {"email": "new@payswap.test", "action_url": "/login/"},
        )
        assert "new@payswap.test" in text
        assert "{{" not in text
        assert subject

    def test_verification_code_uses_support_sender(self, merchant_user):
        with override_settings(
            OTP_FROM_EMAIL="Payswap <support@payswap.in>",
            OTP_REPLY_TO_EMAIL="support@payswap.in",
        ):
            EmailService.send(
                to=merchant_user.email,
                template="verification_code",
                context={"user": merchant_user, "code": "654321"},
                sensitive=True,
            )
        msg = mail.outbox[-1]
        assert "support@payswap.in" in msg.from_email
        assert msg.reply_to == ["support@payswap.in"]
        assert "654321" in msg.body
        assert "Powered by PAYSWAP" in msg.body

    def test_order_rejection_reason_in_email_not_inbox(self, merchant_user):
        NotificationService.notify(
            user=merchant_user,
            title="Order rejected",
            body="Rejected",
            template="order_rejected",
            context={"reason": "quantity exceeds limit", "reference": "ORD-22", "product": "Amazon"},
        )
        combined = mail.outbox[-1].body + mail.outbox[-1].alternatives[0][0]
        assert "quantity exceeds limit" in combined
        inbox = Notification.objects.filter(user=merchant_user).latest("created_at")
        assert "quantity exceeds limit" not in inbox.body
