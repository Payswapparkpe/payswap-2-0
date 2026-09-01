import pytest

from audit.services import AuditService


@pytest.mark.django_db
class TestAuditRedaction:
    def test_redacts_secrets_and_keeps_safe_fields(self, admin_user):
        event = AuditService.record(
            actor=admin_user,
            action="merchant.approve",
            resource_type="merchant",
            resource_id="PSM-000123",
            result="success",
            before={"business_name": "ABC Pvt Ltd", "password": "secret", "otp": "123456"},
            after={
                "status": "ACTIVE",
                "voucher_code": "ABCD-EFGH",
                "account_number": "1234567890",
            },
        )
        assert event.before["business_name"] == "ABC Pvt Ltd"
        assert event.before["password"] == "********"
        assert event.before["otp"] == "********"
        assert event.after["voucher_code"] == "********"
        assert event.after["account_number"] == "********"
        assert event.after["status"] == "ACTIVE"
        assert event.action == "merchant.approve"
