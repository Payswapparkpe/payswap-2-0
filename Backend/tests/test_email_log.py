import pytest
from django.core import mail

from notifications.email_service import EmailService
from notifications.models import DeliveryStatus, EmailLog


@pytest.mark.django_db
class TestEmailLog:
    def test_send_creates_sent_log(self, merchant_user):
        EmailService.send(
            to=merchant_user.email,
            template="generic_notice",
            context={"user": merchant_user, "title": "Hello", "body": "World", "reference": "R1"},
        )
        log = EmailLog.objects.get(recipient=merchant_user.email)
        assert log.status == DeliveryStatus.SENT
        assert log.template_key == "generic_notice"
        assert mail.outbox

    def test_idempotent_skip_when_already_sent(self, merchant_user):
        context = {"user": merchant_user, "title": "Hello", "body": "World", "reference": "R1"}
        EmailService.send(to=merchant_user.email, template="generic_notice", context=context)
        EmailService.send(to=merchant_user.email, template="generic_notice", context=context)
        assert EmailLog.objects.filter(recipient=merchant_user.email).count() == 1
        assert len(mail.outbox) == 1
