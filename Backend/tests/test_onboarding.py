import pytest
from django.core.exceptions import ValidationError

from merchants.services import MerchantOnboardingService
from merchants.states import ApplicationStatus, StepStatus
from tests.support import complete_required_draft


def _start(merchant_user):
    return MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")


@pytest.mark.django_db
class TestOnboardingStateMachine:
    def test_start_creates_draft_with_steps(self, merchant_user):
        application = _start(merchant_user)
        assert application.status == ApplicationStatus.DRAFT
        assert application.public_id.startswith("PSM-")
        assert application.steps.count() == 10
        assert application.merchant.owner == merchant_user

    def test_cannot_submit_until_required_steps_complete(self, merchant_user):
        application = _start(merchant_user)
        with pytest.raises(ValidationError):
            MerchantOnboardingService.submit(application, actor=merchant_user)

    def test_submit_moves_to_submitted(self, merchant_user):
        application = _start(merchant_user)
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        application.refresh_from_db()
        assert application.status == ApplicationStatus.SUBMITTED

    def test_review_can_request_clarification_on_one_step(self, merchant_user, kyc_user):
        application = _start(merchant_user)
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        MerchantOnboardingService.start_review(application, actor=kyc_user)
        MerchantOnboardingService.request_clarification(
            application,
            actor=kyc_user,
            step_key="bank",
            message="Please upload a clearer copy of the cancelled cheque.",
        )
        application.refresh_from_db()
        assert application.status == ApplicationStatus.CLARIFICATION_REQUIRED
        bank = application.steps.get(key="bank")
        assert bank.status == StepStatus.NEEDS_CORRECTION

    def test_rejected_cannot_become_approved_without_resubmit(self, merchant_user, kyc_user):
        application = _start(merchant_user)
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        MerchantOnboardingService.start_review(application, actor=kyc_user)
        MerchantOnboardingService.reject(application, actor=kyc_user, reason="Business information mismatch")
        with pytest.raises(ValidationError):
            MerchantOnboardingService.approve(application, actor=kyc_user)

    def test_private_limited_requires_cin_fields(self, merchant_user):
        application = _start(merchant_user)
        with pytest.raises(ValidationError):
            MerchantOnboardingService.save_step(
                application,
                key="business",
                actor=merchant_user,
                data={"legal_name": "ABC"},
            )
        MerchantOnboardingService.save_step(
            application,
            key="business",
            actor=merchant_user,
            data={
                "legal_name": "ABC Private Limited",
                "cin": "U74999MH2018PTC123456",
                "pan": "ABCDE1234F",
                "gstin": "27ABCDE1234F1Z5",
            },
        )
        step = application.steps.get(key="business")
        assert step.status == StepStatus.COMPLETE
