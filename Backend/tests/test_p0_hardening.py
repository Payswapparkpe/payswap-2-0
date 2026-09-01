"""Regression tests for the 2026-08-17 deep-scan P0 fixes.

Covers: Cashfree settings import (C-1), approval evidence gates (C-3),
encrypted notification payloads (H-1), race-safe public IDs (H-4),
admin audit coverage (H-6), employee search links (H-7).
"""

import pytest
from django.core.exceptions import ValidationError

from accounts.services import VerificationService
from audit.models import AuditEvent
from integrations.cashfree import CashfreeClient
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService, next_public_id
from merchants.states import ApplicationStatus
from notifications.payload import SECURE_CONTEXT_KEY, hydrate_context, protect_context
from portals.search import search
from tests.support import complete_required_draft
from verification.models import Document
from verification.services import DocumentReviewService


@pytest.mark.django_db
class TestIdentityServiceSettings:
    def test_cashfree_client_builds_from_settings_without_patching(self, settings):
        from verification.providers import CashfreeVerificationProvider
        from verification.services import VerificationService as DomainVerificationService

        settings.CASHFREE_CLIENT_ID = "test-client-id"
        settings.CASHFREE_CLIENT_SECRET = "test-client-secret"
        settings.CASHFREE_ENV = "sandbox"
        provider = DomainVerificationService.provider()
        assert isinstance(provider, CashfreeVerificationProvider)
        assert isinstance(provider.client, CashfreeClient)


@pytest.mark.django_db
class TestApprovalEvidenceGates:
    def _submitted(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        return application

    def test_approve_blocked_when_pan_document_unverified(self, merchant_user, admin_user):
        application = self._submitted(merchant_user)
        application.merchant.documents.all().update(status=Document.Status.UNDER_REVIEW)
        MerchantOnboardingService.start_review(application, actor=admin_user)
        with pytest.raises(ValidationError):
            MerchantOnboardingService.approve(application, actor=admin_user)
        application.refresh_from_db()
        assert application.status == ApplicationStatus.UNDER_REVIEW
        application.merchant.refresh_from_db()
        assert application.merchant.status != Merchant.Status.ACTIVE
        assert AuditEvent.objects.filter(action="merchant.approve", result="failure").exists()

    def test_approve_blocked_without_any_documents(self, merchant_user, admin_user):
        application = self._submitted(merchant_user)
        application.merchant.documents.all().delete()
        MerchantOnboardingService.start_review(application, actor=admin_user)
        with pytest.raises(ValidationError):
            MerchantOnboardingService.approve(application, actor=admin_user)
        application.merchant.refresh_from_db()
        assert application.merchant.kyc_status != Merchant.VerificationState.VERIFIED

    def test_rejected_document_blocks_until_verified_replacement(self, merchant_user, admin_user):
        application = self._submitted(merchant_user)
        document = application.merchant.documents.get(doc_type=Document.DocType.PAN)
        DocumentReviewService.reject(document=document, actor=admin_user, reason="Illegible scan")
        MerchantOnboardingService.start_review(application, actor=admin_user)
        with pytest.raises(ValidationError):
            MerchantOnboardingService.approve(application, actor=admin_user)
        DocumentReviewService.approve(document=document, actor=admin_user)
        MerchantOnboardingService.approve(application, actor=admin_user)
        application.merchant.refresh_from_db()
        assert application.merchant.status == Merchant.Status.ACTIVE


@pytest.mark.django_db
class TestPublicIdSequence:
    def test_ids_are_unique_and_monotonic(self, merchant_user, other_merchant_user):
        first = MerchantOnboardingService.start(merchant_user, entity_type="INDIVIDUAL")
        second = MerchantOnboardingService.start(other_merchant_user, entity_type="INDIVIDUAL")
        assert first.public_id != second.public_id
        first_number = int(first.public_id.rsplit("-", 1)[-1])
        second_number = int(second.public_id.rsplit("-", 1)[-1])
        assert second_number > first_number

    def test_sequence_baselines_from_existing_rows(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="INDIVIDUAL")
        Document.objects.create(
            merchant=application.merchant,
            public_id="DOC-000007",
            doc_type=Document.DocType.OTHER,
            uploaded_by=merchant_user,
        )
        assert next_public_id("DOC", Document) == "DOC-000008"


@pytest.mark.django_db
class TestSecureNotificationPayload:
    def test_protect_context_hides_secrets_and_roundtrips(self):
        payload = protect_context({"code": "654321"})
        assert SECURE_CONTEXT_KEY in payload
        assert "654321" not in str(payload)
        assert hydrate_context(payload)["code"] == "654321"

    def test_verification_email_delivers_code_through_secure_payload(self, merchant_user, mailoutbox):
        issued = VerificationService.issue(merchant_user, channel="email")
        assert len(mailoutbox) == 1
        assert issued.debug_code in mailoutbox[0].body


@pytest.mark.django_db
class TestEmployeeSearchLinks:
    def test_employee_merchant_result_links_to_application(self, kyc_user, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        results = search(kyc_user, application.merchant.public_id)
        assert results
        assert results[0]["url"] == f"/employee/queue/{application.public_id}/"

    def test_employee_merchant_without_application_links_to_queue(self, kyc_user, merchant_user):
        Merchant.objects.create(owner=merchant_user, public_id="PSM-009900", entity_type="INDIVIDUAL")
        results = search(kyc_user, "PSM-009900")
        assert results
        assert results[0]["url"] == "/employee/queue/"


@pytest.mark.django_db
class TestAdminAuditCoverage:
    def test_assign_and_suspend_write_audit_events(self, client, admin_user, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="INDIVIDUAL")
        merchant = application.merchant
        client.force_login(admin_user)
        url = f"/administration/merchants/{merchant.public_id}/"
        response = client.post(url, {"action": "assign", "assigned_to": admin_user.pk})
        assert response.status_code == 302
        assert AuditEvent.objects.filter(action="merchant.assign", resource_id=merchant.public_id).exists()
        response = client.post(url, {"action": "suspend"})
        assert response.status_code == 302
        event = AuditEvent.objects.filter(action="merchant.suspend", resource_id=merchant.public_id).first()
        assert event is not None
        assert event.ip_address is not None
