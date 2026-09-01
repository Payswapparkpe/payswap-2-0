"""Merchant onboarding wizard and collect-first verification UX."""

import pytest

from merchants.privacy import decrypt_step_data
from merchants.services import MerchantOnboardingService
from merchants.states import StepStatus
from verification.models import BankAccount
from verification.services import VerificationService


@pytest.mark.django_db
class TestOnboardingWizard:
    def test_business_save_completes_kyc_and_kyb_without_reentry(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        MerchantOnboardingService.save_step(
            application,
            key="business",
            actor=merchant_user,
            data={
                "legal_name": "Northwind Payments Private Limited",
                "cin": "U74999MH2018PTC123456",
                "pan": "ABCDE1234F",
                "gstin": "27ABCDE1234F1Z5",
                "registered_office": "12 MG Road",
                "pincode": "400001",
            },
        )
        kyc = decrypt_step_data(application.steps.get(key="kyc").data)
        kyb = decrypt_step_data(application.steps.get(key="kyb").data)
        assert application.steps.get(key="kyc").status == StepStatus.COMPLETE
        assert application.steps.get(key="kyb").status == StepStatus.COMPLETE
        assert kyc["pan"] == "ABCDE1234F"
        assert kyb["gstin"] == "27ABCDE1234F1Z5"

    def test_wizard_hides_legacy_kyc_kyb_steps(self, client, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)
        html = client.get(f"/merchant/onboarding/{application.public_id}/").content.decode()
        assert html.count("stepper-item") == 5
        assert "?step=kyc" not in html
        assert "?step=kyb" not in html
        assert "Legal name" in html
        response = client.get(f"/merchant/onboarding/{application.public_id}/?step=kyc")
        assert response.status_code == 302
        assert "step=business" in response["Location"]

    def test_bank_save_persists_encrypted_account_for_later_verify(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        step = MerchantOnboardingService.save_step(
            application,
            key="bank",
            actor=merchant_user,
            data={
                "account_holder": "Northwind Payments Private Limited",
                "account_number": "50100012345678",
                "ifsc": "HDFC0001234",
            },
        )
        assert step.data["account_number"] == "****5678"
        account = BankAccount.objects.get(merchant=application.merchant)
        assert account.get_account_number() == "50100012345678"
        assert account.verified is False

    def test_business_save_mirrors_owners_for_individual(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="INDIVIDUAL")
        MerchantOnboardingService.save_step(
            application,
            key="business",
            actor=merchant_user,
            data={
                "legal_name": "Sandeep Kumar",
                "brand_name": "Sandeep Kumar",
                "pan": "ABCDE1234F",
                "owner_name": "Sandeep Kumar",
                "owner_dob": "1990-01-01",
                "authorized_signatory": "Sandeep Kumar",
                "designation": "self",
            },
        )
        owners = application.steps.get(key="owners")
        assert owners.status == StepStatus.COMPLETE
        assert decrypt_step_data(owners.data)["owner_name"] == "Sandeep Kumar"

    def test_api_onboarding_put_uses_step_not_navigation_target(self, client, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="INDIVIDUAL")
        client.force_login(merchant_user)
        response = client.put(
            "/api/merchant/onboarding/",
            data={
                "step": "profile",
                "currentStep": "bank",
                "profile": {
                    "brandName": "Sandeep Kumar",
                    "legalName": "Sandeep Kumar",
                    "entityType": "individual",
                },
                "signatory": {
                    "name": "Sandeep Kumar",
                    "pan": "ABCDE1234F",
                    "dob": "1990-01-01",
                },
                "bank": {},
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        application.refresh_from_db()
        business = application.steps.get(key="business")
        bank = application.steps.get(key="bank")
        assert business.status == StepStatus.IN_PROGRESS
        assert bank.status == StepStatus.NOT_STARTED
        assert response.json()["currentStep"] == "profile"


@pytest.mark.django_db
class TestAgreementPreviewAndVerificationCentre:
    def test_agreements_page_shows_draft_preview_before_issue(self, client, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        MerchantOnboardingService.save_step(
            application,
            key="business",
            actor=merchant_user,
            data={
                "legal_name": "Northwind Payments Private Limited",
                "cin": "U74999MH2018PTC123456",
                "pan": "ABCDE1234F",
                "gstin": "27ABCDE1234F1Z5",
            },
        )
        client.force_login(merchant_user)
        html = client.get("/merchant/agreements/").content.decode()
        assert "Draft voucher supply agreement" in html
        assert "Northwind Payments Private Limited" in html
        assert "AGREEMENT FOR SUPPLY OF BRAND VOUCHERS" in html
        assert "js-datatable" not in html or "No agreement" in html or "Draft" in html

    def test_verification_centre_does_not_reask_pan_gstin_bank(self, client, merchant_user):
        MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)
        html = client.get("/merchant/verification/").content.decode()
        assert 'name="pan"' not in html
        assert 'name="gstin"' not in html
        assert 'name="account_number"' not in html
        assert "Verify collected details" in html

    def test_verify_collected_skips_when_identifiers_missing(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        records = VerificationService.verify_collected(merchant=application.merchant, actor=merchant_user)
        assert records == []
