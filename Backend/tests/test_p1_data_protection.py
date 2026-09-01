"""Regression tests for P1 data-protection and audit hardening."""

import json

import pytest

from agreements.services import AgreementService
from agreements.template import render_voucher_supply_agreement
from audit.models import AuditEvent
from audit.services import redact
from merchants.models import BeneficialOwner
from merchants.privacy import decrypt_step_data, display_step_data
from merchants.services import MerchantOnboardingService
from tests.support import complete_required_draft

BUSINESS_DATA = {
    "legal_name": "Sharma Digital Services Private Limited",
    "cin": "U74999MH2018PTC123456",
    "pan": "ABCDE1234F",
    "gstin": "27ABCDE1234F1Z5",
}


@pytest.mark.django_db
class TestStepPiiEncryption:
    def test_sensitive_fields_encrypted_at_rest(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        step = MerchantOnboardingService.save_step(
            application, key="business", actor=merchant_user, data=dict(BUSINESS_DATA)
        )
        step.refresh_from_db()
        raw = json.dumps(step.data)
        assert "ABCDE1234F" not in raw
        assert "27ABCDE1234F1Z5" not in raw
        assert "U74999MH2018PTC123456" not in raw
        assert step.data["pan"].startswith("gAAAA")
        assert step.data["legal_name"] == BUSINESS_DATA["legal_name"]

    def test_decrypt_round_trip_for_privileged_consumers(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        step = MerchantOnboardingService.save_step(
            application, key="business", actor=merchant_user, data=dict(BUSINESS_DATA)
        )
        step.refresh_from_db()
        revealed = decrypt_step_data(step.data)
        assert revealed["pan"] == "ABCDE1234F"
        assert revealed["gstin"] == "27ABCDE1234F1Z5"

    def test_display_masks_sensitive_fields(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        step = MerchantOnboardingService.save_step(
            application, key="business", actor=merchant_user, data=dict(BUSINESS_DATA)
        )
        step.refresh_from_db()
        display = display_step_data(step.data)
        assert display["pan"].endswith("234F")
        assert "ABCDE" not in display["pan"]
        assert display["legal_name"] == BUSINESS_DATA["legal_name"]

    def test_masked_resubmission_keeps_stored_value(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        step = MerchantOnboardingService.save_step(
            application, key="business", actor=merchant_user, data=dict(BUSINESS_DATA)
        )
        step.refresh_from_db()
        masked = display_step_data(step.data)
        # Simulate a form resubmit where the merchant left the masked PAN untouched.
        payload = dict(BUSINESS_DATA, pan=masked["pan"], gstin=masked["gstin"], cin=masked["cin"])
        # Force back to an editable state, as clarification flow would.
        from merchants.states import ApplicationStatus

        application.status = ApplicationStatus.CLARIFICATION_REQUIRED
        application.save(update_fields=["status"])
        step.status = "PENDING"
        step.save(update_fields=["status"])
        MerchantOnboardingService.save_step(application, key="business", actor=merchant_user, data=payload)
        step.refresh_from_db()
        assert decrypt_step_data(step.data)["pan"] == "ABCDE1234F"

    def test_legacy_plaintext_rows_still_readable(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        step = application.steps.get(key="business")
        step.data = dict(BUSINESS_DATA)  # row as written before encryption-at-rest
        step.save(update_fields=["data"])
        step.refresh_from_db()
        assert decrypt_step_data(step.data)["pan"] == "ABCDE1234F"
        assert display_step_data(step.data)["pan"].endswith("234F")

    def test_agreement_body_uses_decrypted_identifiers(self, merchant_user, admin_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        MerchantOnboardingService.start_review(application, actor=admin_user)
        MerchantOnboardingService.approve(application, actor=admin_user)
        body, snapshot = render_voucher_supply_agreement(application.merchant)
        assert "ABCDE1234F" in body
        assert snapshot["second_party"]["pan"] == "ABCDE1234F"
        agreement = AgreementService.generate(merchant=application.merchant, actor=admin_user)
        assert "ABCDE1234F" in agreement.body


@pytest.mark.django_db
class TestBeneficialOwnerEncryption:
    def test_pan_stored_encrypted_with_last4(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        owner = BeneficialOwner(merchant=application.merchant, full_name="Test Owner")
        owner.set_pan("ABCDE1234F")
        owner.save()
        owner.refresh_from_db()
        assert owner.pan_encrypted.startswith("gAAAA")
        assert "ABCDE1234F" not in owner.pan_encrypted
        assert owner.pan_last4 == "234F"
        assert owner.pan == "ABCDE1234F"


@pytest.mark.django_db
class TestAuditHardening:
    def test_user_agent_and_ip_recorded_when_request_present(self, rf, admin_user):
        from audit.services import AuditService

        request = rf.get("/administration/audit/", HTTP_USER_AGENT="TestAgent/1.0")
        AuditService.record(actor=admin_user, action="test.ping", request=request)
        event = AuditEvent.objects.get(action="test.ping")
        assert event.user_agent == "TestAgent/1.0"
        assert event.ip_address

    def test_redact_covers_otp_code_and_client_secret(self):
        payload = {"context": {"code": "123456", "client_secret": "abc", "note": "ok"}}
        cleaned = redact(payload)
        assert cleaned["context"]["code"] == "********"
        assert cleaned["context"]["client_secret"] == "********"
        assert cleaned["context"]["note"] == "ok"
