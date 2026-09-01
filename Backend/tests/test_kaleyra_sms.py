import pytest

from integrations.kaleyra import KaleyraClient
from tests.test_integrations import FakeHttp


@pytest.mark.django_db
class TestKaleyraSms:
    def test_json_payload_includes_dlt_fields(self):
        http = FakeHttp({"json": {"sms": [{"message_id": "m-1"}]}})
        client = KaleyraClient(
            sid="HXTEST",
            api_key="secret",
            sender="PAYSWAP",
            base_url="https://api.in.kaleyra.io",
            http=http,
        )
        client.send_sms(
            to="9876543210",
            body="Order ORD-1 submitted.",
            sms_type="TXN",
            template_id="DLT-1",
            entity_id="ENT-1",
        )
        payload = http.calls[0]["json"]
        assert http.calls[0]["url"] == "https://api.in.kaleyra.io/v1/HXTEST/sms/json"
        assert payload["sms"][0]["to"] == "+919876543210"
        assert payload["sms"][0]["template_id"] == "DLT-1"
        assert payload["entity_id"] == "ENT-1"
        assert payload["type"] == "TXN"
