import pytest

from audit.models import AuditEvent
from notifications.email_service import EmailService
from notifications.services import NotificationService


@pytest.mark.django_db
class TestNotificationAudit:
    def test_email_send_writes_audit_event(self, merchant_user):
        EmailService.send(
            to=merchant_user.email,
            template="generic_notice",
            context={"user": merchant_user, "title": "Ping", "body": "Pong"},
        )
        assert AuditEvent.objects.filter(action="notification.email_sent").exists()

    def test_rejection_reason_stays_out_of_in_app_body(self, merchant_user):
        notice = NotificationService.notify(
            user=merchant_user,
            title="Order rejected",
            body="Rejected",
            template="order_rejected",
            context={"reason": "incomplete KYC documents", "reference": "ORD-9"},
        )
        assert "incomplete KYC" not in notice.body
        assert "Sign in" in notice.body
