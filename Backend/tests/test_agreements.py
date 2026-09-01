import pytest
from django.core.exceptions import ValidationError

from agreements.models import Agreement
from agreements.services import AgreementService
from agreements.template import render_voucher_supply_agreement, verification_complete
from merchants.services import MerchantOnboardingService
from tests.support import complete_required_draft


@pytest.mark.django_db
class TestAgreementKycGate:
    def test_generate_blocked_before_verification(self, merchant_user, admin_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        complete_required_draft(application)
        with pytest.raises(ValidationError, match="KYC, KYB, and bank verification"):
            AgreementService.generate(merchant=application.merchant, actor=admin_user)

    def test_click_wrap_signing_is_rejected(self, merchant_user, admin_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        MerchantOnboardingService.start_review(application, actor=admin_user)
        MerchantOnboardingService.approve(application, actor=admin_user)
        agreement = application.merchant.agreements.get()
        with pytest.raises(ValidationError, match="Aadhaar eSign"):
            AgreementService.merchant_sign(agreement=agreement, actor=merchant_user)

    def test_esign_blocked_until_kyc_verified(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        agreement = Agreement.objects.create(
            merchant=application.merchant,
            public_id="AGR-TEST1",
            body="placeholder",
            status=Agreement.Status.MERCHANT_REVIEW,
        )
        with pytest.raises(ValidationError, match="KYC, KYB, and bank verification"):
            AgreementService.start_esign(agreement=agreement, actor=merchant_user)

    def test_approve_issues_prefilled_agreement(self, merchant_user, admin_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        MerchantOnboardingService.start_review(application, actor=admin_user)
        MerchantOnboardingService.approve(application, actor=admin_user)
        merchant = application.merchant
        merchant.refresh_from_db()
        assert verification_complete(merchant)
        agreement = merchant.agreements.get()
        assert agreement.status == Agreement.Status.MERCHANT_REVIEW
        assert agreement.template_version == "voucher-supply-2"
        assert agreement.document_file
        assert "SCHEDULE B" in agreement.body
        assert "12 MG Road" in agreement.body
        assert "Test Signatory" in agreement.body or merchant.owner.name in agreement.body
        assert "ABCDE1234F" in agreement.body
        second = agreement.generated_from["second_party"]
        assert second["office"].startswith("12 MG Road")
        assert second["pan"] == "ABCDE1234F"

    def test_issue_if_ready_is_idempotent(self, merchant_user, admin_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        MerchantOnboardingService.start_review(application, actor=admin_user)
        MerchantOnboardingService.approve(application, actor=admin_user)
        first = application.merchant.agreements.get()
        again = AgreementService.issue_if_verification_complete(
            merchant=application.merchant, actor=admin_user
        )
        assert again.pk == first.pk
        assert application.merchant.agreements.count() == 1

    def test_render_prefills_verified_particulars(self, merchant_user, admin_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        MerchantOnboardingService.start_review(application, actor=admin_user)
        MerchantOnboardingService.approve(application, actor=admin_user)
        body, snapshot = render_voucher_supply_agreement(application.merchant)
        assert "AGREEMENT FOR SUPPLY OF BRAND VOUCHERS & GIFT CARDS" in body
        assert snapshot["second_party"]["gstin"] == "27ABCDE1234F1Z5"
        assert "Aadhaar eSign" in body


@pytest.mark.django_db
class TestAgreementPortal:
    def test_merchant_page_blocks_esign_before_kyc(self, client, merchant_user):
        MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)
        html = client.get("/merchant/agreements/").content.decode()
        assert "Verification required" in html
        assert "Aadhaar eSign" in html
        assert "KYC is Not started" in html
        response = client.post("/merchant/agreements/", {"action": "esign"})
        assert response.status_code == 302
