"""Business profile by entity type, and 70% document-to-profile matching."""

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from merchants.matching import MATCH_THRESHOLD, assert_document_matches_profile, score_identifiers
from merchants.privacy import decrypt_step_data
from merchants.services import MerchantOnboardingService
from verification.models import Document


@pytest.mark.django_db
class TestBusinessProfile:
    def test_profile_collects_pan_and_dob_for_entity(self, client, merchant_user):
        client.force_login(merchant_user)
        html = client.get("/merchant/profile/").content.decode()
        assert "Type of business" in html
        assert 'name="pan"' in html
        assert 'name="owner_dob"' in html
        assert "paper-sheet" in html
        response = client.post(
            "/merchant/profile/",
            {
                "action": "business",
                "entity_type": "INDIVIDUAL",
                "legal_name": "Priya Sharma",
                "pan": "ABCDE1234F",
                "owner_dob": "1990-01-15",
                "owner_name": "Priya Sharma",
            },
        )
        assert response.status_code == 302
        merchant_user.refresh_from_db()
        merchant = merchant_user.merchant
        assert merchant.entity_type == "INDIVIDUAL"
        application = merchant.applications.first()
        business = decrypt_step_data(application.steps.get(key="business").data)
        owners = decrypt_step_data(application.steps.get(key="owners").data)
        assert business["pan"] == "ABCDE1234F"
        assert owners["owner_dob"] == "1990-01-15"

    def test_private_limited_requires_gstin_and_cin(self, client, merchant_user):
        client.force_login(merchant_user)
        response = client.post(
            "/merchant/profile/",
            {
                "action": "business",
                "entity_type": "PRIVATE_LIMITED",
                "legal_name": "Northwind Payments Private Limited",
                "pan": "ABCDE1234F",
                "owner_dob": "1990-01-15",
            },
        )
        assert response.status_code == 302
        merchant_user.refresh_from_db()
        application = merchant_user.merchant.applications.first()
        business = decrypt_step_data(application.steps.get(key="business").data)
        assert not business.get("pan")


@pytest.mark.django_db
class TestDocumentProfileMatch:
    def test_score_identifiers_near_match_passes_threshold(self):
        assert score_identifiers("ABCDE1234F", "ABCDE1234F") == 100
        assert score_identifiers("ABCDE1234F", "ABCDE1234E") >= MATCH_THRESHOLD
        assert score_identifiers("ABCDE1234F", "ZZZZZ9999Z") < MATCH_THRESHOLD

    def test_upload_rejected_below_threshold(self, client, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="INDIVIDUAL")
        MerchantOnboardingService.save_step(
            application,
            key="business",
            actor=merchant_user,
            data={"legal_name": "Priya Sharma", "pan": "ABCDE1234F"},
        )
        MerchantOnboardingService.save_step(
            application,
            key="owners",
            actor=merchant_user,
            data={"owner_name": "Priya Sharma", "owner_dob": "1990-01-15"},
        )
        client.force_login(merchant_user)
        response = client.post(
            "/merchant/documents/",
            {
                "doc_type": "PAN",
                "document_number": "ZZZZZ9999Z",
                "file": SimpleUploadedFile("pan.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            },
        )
        assert response.status_code == 302
        assert not Document.objects.filter(merchant=application.merchant).exists()

    def test_upload_accepted_when_pan_matches(self, client, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="INDIVIDUAL")
        MerchantOnboardingService.save_step(
            application,
            key="business",
            actor=merchant_user,
            data={"legal_name": "Priya Sharma", "pan": "ABCDE1234F"},
        )
        MerchantOnboardingService.save_step(
            application,
            key="owners",
            actor=merchant_user,
            data={"owner_name": "Priya Sharma", "owner_dob": "1990-01-15"},
        )
        client.force_login(merchant_user)
        response = client.post(
            "/merchant/documents/",
            {
                "doc_type": "PAN",
                "document_number": "ABCDE1234F",
                "holder_name": "Priya Sharma",
                "file": SimpleUploadedFile("pan.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            },
        )
        assert response.status_code == 302
        document = Document.objects.get(merchant=application.merchant)
        assert document.doc_type == "PAN"
        match = assert_document_matches_profile(
            merchant=application.merchant,
            doc_type="PAN",
            document_number="ABCDE1234F",
            holder_name="Priya Sharma",
        )
        assert match["ok"]
        assert match["score"] >= MATCH_THRESHOLD

    def test_upload_blocked_until_profile_has_pan(self, merchant_user):
        MerchantOnboardingService.start(merchant_user, entity_type="INDIVIDUAL")
        with pytest.raises(ValidationError, match="profile"):
            assert_document_matches_profile(
                merchant=merchant_user.merchant,
                doc_type="PAN",
                document_number="ABCDE1234F",
            )
