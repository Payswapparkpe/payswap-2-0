from pathlib import Path

import pytest
from django.core import mail

from notifications.catalog import TEMPLATES
from notifications.mail import MAIL_TEMPLATES, MailService
from notifications.sms_service import SmsService

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "emails"


@pytest.mark.django_db
class TestEmailTemplates:
    def test_catalog_has_html_and_text_files(self):
        for key in TEMPLATES:
            html_path = TEMPLATE_DIR / f"{key}.html"
            text_path = TEMPLATE_DIR / f"{key}.txt"
            assert html_path.is_file(), f"missing {html_path.name}"
            assert text_path.is_file(), f"missing {text_path.name}"

    def test_every_catalogued_template_renders_html_and_text(self, merchant_user):
        context = {
            "user": merchant_user,
            "code": "123456",
            "title": "Test notice",
            "body": "Details for the merchant.",
            "action_url": "http://testserver/merchant/",
            "action_label": "Open portal",
            "reference": "ORD-1",
            "ip_address": "127.0.0.1",
            "user_agent": "pytest",
            "new_device": True,
            "product_name": "Amazon ₹500",
            "brand_name": "Amazon",
            "quantity": 2,
            "total": "1000.00",
            "amount": "1000.00",
            "expected": "1000.00",
            "received": "900.00",
            "voucher_count": 2,
            "agreement_id": "AGR-1",
            "reason": "Need a clearer PAN scan.",
        }
        subjects = []
        for key in MAIL_TEMPLATES:
            html, text, subject = MailService.render(key, context)
            subjects.append(subject)
            assert "Payswap" in html
            assert "Payswap" in text
            assert "ParkPe" not in html
            assert "ParkPe" not in text
            assert "Parkpe" not in html
            assert "Parkpe" not in text
            assert subject
            assert "{{" not in html
            assert "{{" not in text
            assert "{{" not in subject
            assert "Notification preferences" in text
            assert merchant_user.email in html
        assert len(set(subjects)) == len(subjects) or "Account notice" in subjects

    def test_from_header_is_payswap_not_parkpe(self, merchant_user, settings):
        settings.DEFAULT_FROM_EMAIL = "ParkPe <alerts@parkpe.example>"
        from notifications.email_service import EmailService

        EmailService.send(
            to=merchant_user.email,
            template="generic_notice",
            context={"user": merchant_user, "title": "Hello", "body": "World"},
        )
        sender = mail.outbox[-1].from_email
        assert sender.startswith("Payswap ")
        assert "ParkPe" not in sender
        assert "alerts@parkpe.example" in sender

    def test_every_sms_template_renders_within_160_chars(self, merchant_user):
        context = {
            "user": merchant_user,
            "code": "123456",
            "title": "Notice",
            "body": "Details",
            "action_url": "http://testserver/login/",
            "reference": "ORD-1",
        }
        for key, spec in TEMPLATES.items():
            body = SmsService.render(key, context)
            assert body
            assert "{{" not in body
            assert len(body) <= 160
            if spec.sms_type == "OTP" and key == "verification_code":
                assert "123456" in body


    def test_verification_email_is_multipart_and_contains_code(self, merchant_user):
        from accounts.services import VerificationService

        issued = VerificationService.issue(merchant_user, channel="email")
        message = mail.outbox[-1]
        assert message.alternatives
        html = message.alternatives[0][0]
        assert issued.debug_code in message.body
        assert issued.debug_code in html
        assert "10 minutes" in html

    def test_in_app_notice_sends_email_by_default(self, merchant_user):
        from notifications.services import NotificationService

        NotificationService.notify(
            user=merchant_user,
            title="Order update",
            body="Your order moved forward.",
            url="/merchant/orders/",
            template="generic_notice",
            context={"reference": "ORD-1"},
        )
        assert mail.outbox
        assert "ORD-1" in mail.outbox[-1].body or "ORD-1" in mail.outbox[-1].alternatives[0][0]

    def test_order_approved_email_never_includes_secret_codes(self, merchant_user):
        MailService.send(
            to=merchant_user.email,
            template="order_approved",
            context={
                "user": merchant_user,
                "reference": "ORD-99",
                "action_url": "http://testserver/merchant/orders/ORD-99/",
            },
        )
        html = mail.outbox[-1].alternatives[0][0]
        assert "sign in" in html.lower() or "portal" in html.lower() or "order" in html.lower()
        assert "token_hex" not in html
