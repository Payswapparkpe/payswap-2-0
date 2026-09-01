import pytest

from notifications.models import DeliveryStatus, SmsLog
from notifications.sms_service import SmsService


@pytest.mark.django_db
class TestSmsLog:
    def test_send_records_queued_or_sent_log(self, merchant_user, monkeypatch):
        merchant_user.mobile = "9876543210"
        merchant_user.save(update_fields=["mobile"])

        class FakeClient:
            configured = True

            def send_sms(self, *, to, body, **kwargs):
                return {"id": "sms-log-1", "sms": [{"message_id": "mid-1"}]}

        monkeypatch.setattr(SmsService, "client", staticmethod(lambda: FakeClient()))
        SmsService.send(
            to=merchant_user.mobile,
            template="verification_code",
            context={"user": merchant_user, "code": "123456"},
            sensitive=True,
        )
        log = SmsLog.objects.get(recipient=merchant_user.mobile)
        assert log.status == DeliveryStatus.SENT
        assert log.provider_message_id == "mid-1"

    def test_idempotent_skip_when_already_sent(self, merchant_user, monkeypatch):
        calls = []

        class FakeClient:
            configured = True

            def send_sms(self, *, to, body, **kwargs):
                calls.append(body)
                return {"id": "sms-log-2"}

        monkeypatch.setattr(SmsService, "client", staticmethod(lambda: FakeClient()))
        context = {"user": merchant_user, "code": "123456"}
        SmsService.send(to="9876543210", template="verification_code", context=context, sensitive=True)
        SmsService.send(to="9876543210", template="verification_code", context=context, sensitive=True)
        assert SmsLog.objects.filter(recipient="9876543210").count() == 1
        assert len(calls) == 1
