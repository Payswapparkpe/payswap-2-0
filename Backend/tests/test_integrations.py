import pytest

from integrations.cashfree import CashfreeClient, CashfreeError
from integrations.kaleyra import KaleyraClient
from merchants.services import MerchantOnboardingService
from tests.support import complete_required_draft
from verification.models import VerificationRecord
from verification.providers import CashfreeVerificationProvider
from verification.services import DocumentReviewService, VerificationService


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def _respond(self, url):
        key = url.rstrip("/").split("/")[-1]
        if key in self.responses:
            return 200, self.responses[key]
        for fragment, payload in self.responses.items():
            if fragment in url:
                return 200, payload
        return 200, {"status": "SUCCESS"}

    def json_request(self, method, url, *, headers=None, json=None, files=None, timeout=20):
        self.calls.append({"method": method, "url": url, "json": json, "headers": headers, "files": files})
        return self._respond(url)

    def get_json(self, url, *, headers=None, params=None, timeout=20):
        self.calls.append({"method": "GET", "url": url, "params": params})
        return self._respond(url)

    def download(self, url, *, timeout=60):
        return b"%PDF-signed"


@pytest.mark.django_db
class TestKaleyraAndCashfree:
    def test_kaleyra_sends_otp_payload(self):
        http = FakeHttp({"messages": {"id": "sms-1"}})
        client = KaleyraClient(
            sid="HXTEST",
            api_key="secret",
            sender="PAYSWP",
            base_url="https://api.in.kaleyra.io",
            http=http,
        )
        client.send_sms(to="9876543210", body="PayswapHub code 123456")
        assert http.calls
        payload = http.calls[0]["json"]
        assert http.calls[0]["url"].endswith("/sms/json")
        assert payload["sms"][0]["to"] == "+919876543210"
        assert payload["from"] == "PAYSWP"
        assert payload["type"] == "OTP"
        assert http.calls[0]["headers"]["api-key"] == "secret"

    def test_mobile_otp_uses_messaging_service(self, merchant_user, monkeypatch):
        merchant_user.mobile = "9876543210"
        merchant_user.save(update_fields=["mobile"])
        sent = []

        class FakeKaleyra:
            configured = True

            def send_sms(self, *, to, body, **kwargs):
                sent.append((to, body))
                return {"id": "local"}

        monkeypatch.setattr(
            "notifications.sms_service.SmsService.client", staticmethod(lambda: FakeKaleyra())
        )
        from accounts.services import VerificationService as OtpService

        issued = OtpService.issue(merchant_user, channel="mobile")
        assert sent
        assert issued.debug_code in sent[0][1]

    def _provider(self, responses, monkeypatch):
        http = FakeHttp(responses)
        client = CashfreeClient(client_id="id", client_secret="sec", environment="sandbox", http=http)
        provider = CashfreeVerificationProvider(client)
        monkeypatch.setattr(VerificationService, "provider", staticmethod(lambda: provider))
        return http

    def test_pan_gstin_bank_and_document_number(self, merchant_user, monkeypatch):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        merchant = application.merchant
        self._provider(
            {
                "pan-lite": {"pan_status": "VALID", "name": "ABC PRIVATE LIMITED", "reference_id": 101},
                "gstin": {
                    "gst_in_status": "Active",
                    "legal_name_of_business": "ABC PRIVATE LIMITED",
                    "reference_id": 102,
                },
                "sync": {
                    "account_status": "VALID",
                    "name_at_bank": "ABC PRIVATE LIMITED",
                    "reference_id": 103,
                },
            },
            monkeypatch,
        )

        pan = VerificationService.verify_pan(
            merchant=merchant,
            actor=merchant_user,
            pan="ABCDE1234F",
            name="ABC PRIVATE LIMITED",
            dob="1990-01-01",
        )
        gst = VerificationService.verify_gstin(
            merchant=merchant,
            actor=merchant_user,
            gstin="27ABCDE1234F1Z5",
        )
        bank = VerificationService.verify_bank(
            merchant=merchant,
            actor=merchant_user,
            account_number="123456789012",
            ifsc="HDFC0001234",
            name="ABC PRIVATE LIMITED",
        )
        assert pan.status == VerificationRecord.Status.VERIFIED
        assert gst.status == VerificationRecord.Status.VERIFIED
        assert bank.status == VerificationRecord.Status.VERIFIED
        assert pan.document_masked == "ABCDE****F"
        assert bank.document_masked == "XXXXXX9012"
        assert pan.get_document() == "ABCDE1234F"
        assert pan.reference_id == "101"
        merchant.refresh_from_db()
        assert merchant.kyc_status == "VERIFIED"
        assert merchant.kyb_status == "VERIFIED"
        assert merchant.bank_status == "VERIFIED"
        document = DocumentReviewService.register_upload(
            merchant=merchant,
            actor=merchant_user,
            doc_type="PAN",
            uploaded_file=None,
            document_number="ABCDE1234F",
        )
        assert document.document_last4 == "234F"
        assert document.get_document_number() == "ABCDE1234F"

    def test_esign_creates_provider_request(self, merchant_user, admin_user, monkeypatch):
        from agreements.services import AgreementService
        from integrations.services import ESignService

        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        http = FakeHttp(
            {
                "esignature/document": {"document_id": 36},
                "esignature": {
                    "status": "SUCCESS",
                    "verification_id": "v-1",
                    "reference_id": 33,
                    "signing_link": "https://sandbox.cashfree.com/esign/sign/abc",
                },
            }
        )
        client = CashfreeClient(client_id="id", client_secret="sec", environment="sandbox", http=http)
        monkeypatch.setattr(ESignService, "cashfree", staticmethod(lambda: client))
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        MerchantOnboardingService.start_review(application, actor=admin_user)
        MerchantOnboardingService.approve(application, actor=admin_user)
        agreement = AgreementService.generate(merchant=application.merchant, actor=admin_user)
        link = AgreementService.start_esign(agreement=agreement, actor=merchant_user)
        agreement.refresh_from_db()
        assert agreement.esign_document_id == "36"
        assert agreement.esign_request_id == "33"
        assert agreement.esign_status == "SENT"
        assert link == "https://sandbox.cashfree.com/esign/sign/abc"
        # Upload went out as multipart PDF.
        upload_call = next(c for c in http.calls if c["url"].endswith("/esignature/document"))
        assert upload_call["files"]["document"][1].startswith(b"%PDF")

    def test_cashfree_rejects_unconfigured_live_call(self):
        client = CashfreeClient(client_id="", client_secret="", environment="sandbox")
        with pytest.raises(CashfreeError):
            client.verify_pan_lite(verification_id="t-1", pan="ABCDE1234F", name="A B", dob="1990-01-01")
