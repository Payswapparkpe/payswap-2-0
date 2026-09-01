"""Wizard uploads must reach the database and be visible to a reviewer.

Files used to stay in the browser as base64 `dataUrl`s, so `merchant.documents`
was empty and the admin Documents tab had nothing to review.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from api.serializers import onboarding_payload
from merchants.services import MerchantOnboardingService
from verification.models import Document
from verification.slots import doc_type_for_slot

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00"
    b"\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _png(name="deed.png"):
    return SimpleUploadedFile(name, PNG, content_type="image/png")


class TestSlotMapping:
    @pytest.mark.parametrize(
        "slot,expected",
        [
            ("board_resolution", Document.DocType.BOARD_RESOLUTION),
            ("moa", Document.DocType.MOA),
            ("penny_proof", Document.DocType.BANK_PROOF),
            ("auth_signatory_pan", Document.DocType.PAN),
            ("partnership_deed", Document.DocType.PARTNERSHIP_DEED),
        ],
    )
    def test_known_slots_resolve(self, slot, expected):
        assert doc_type_for_slot(slot) == expected

    def test_unknown_slot_falls_back_to_other(self):
        """An unmapped dropzone must still upload rather than 400."""
        assert doc_type_for_slot("some_new_slot") == Document.DocType.OTHER

    def test_slot_ids_all_fit_the_column(self):
        from verification.slots import SLOT_DOC_TYPES

        assert all(len(slot) <= 40 for slot in SLOT_DOC_TYPES)
        assert all(len(value) <= 20 for value in Document.DocType.values)


@pytest.mark.django_db
class TestUploadEndpoint:
    def test_upload_creates_document_row(self, client, merchant_user):
        MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)

        response = client.post(
            "/api/merchant/onboarding/documents/",
            {"slotId": "board_resolution", "file": _png("bor.png")},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["publicId"].startswith("DOC")
        assert body["slotId"] == "board_resolution"
        assert body["reviewStatus"] == "under_review"

        doc = Document.objects.get(public_id=body["publicId"])
        assert doc.doc_type == Document.DocType.BOARD_RESOLUTION
        assert doc.slot_id == "board_resolution"
        assert doc.file

    def test_upload_requires_a_file(self, client, merchant_user):
        MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)

        response = client.post("/api/merchant/onboarding/documents/", {"slotId": "moa"})

        assert response.status_code == 400

    def test_upload_requires_a_slot(self, client, merchant_user):
        MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)

        response = client.post("/api/merchant/onboarding/documents/", {"file": _png()})

        assert response.status_code == 400

    def test_reupload_supersedes_the_previous_file(self, client, merchant_user):
        MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)

        first = client.post(
            "/api/merchant/onboarding/documents/",
            {"slotId": "moa", "file": _png("first.png")},
        ).json()
        second = client.post(
            "/api/merchant/onboarding/documents/",
            {"slotId": "moa", "file": _png("second.png")},
        ).json()

        assert first["publicId"] != second["publicId"]
        remaining = Document.objects.filter(slot_id="moa")
        assert remaining.count() == 1
        assert remaining.first().public_id == second["publicId"]
        assert remaining.first().version == 2

    def test_upload_is_scoped_to_the_caller(self, client, merchant_user, other_merchant_user):
        MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        other = MerchantOnboardingService.start(other_merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)

        client.post(
            "/api/merchant/onboarding/documents/",
            {"slotId": "moa", "file": _png()},
        )

        assert other.merchant.documents.count() == 0


@pytest.mark.django_db
class TestPayloadVisibility:
    def test_uploaded_document_appears_in_onboarding_payload(self, client, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)
        client.post(
            "/api/merchant/onboarding/documents/",
            {"slotId": "board_resolution", "file": _png("bor.png")},
        )

        out = onboarding_payload(
            user=merchant_user, application=application, merchant=application.merchant
        )
        slots = {doc["slotId"]: doc for doc in out["documents"]}
        assert "board_resolution" in slots
        assert slots["board_resolution"]["publicId"].startswith("DOC")

    def test_bank_proof_and_registry_deed_use_the_same_upload_path(self, client, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PARTNERSHIP")
        client.force_login(merchant_user)
        client.post(
            "/api/merchant/onboarding/documents/",
            {"slotId": "penny_proof", "file": _png("cheque.png")},
        )
        client.post(
            "/api/merchant/onboarding/documents/",
            {"slotId": "partnership_deed", "file": _png("deed.png")},
        )

        out = onboarding_payload(
            user=merchant_user, application=application, merchant=application.merchant
        )
        assert out["bank"]["proofFile"]["publicId"].startswith("DOC")
        assert out["registryDeedDoc"]["slotId"] == "partnership_deed"

    def test_review_verdict_is_exposed_to_the_wizard(self, client, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)
        body = client.post(
            "/api/merchant/onboarding/documents/",
            {"slotId": "moa", "file": _png()},
        ).json()
        Document.objects.filter(public_id=body["publicId"]).update(
            status=Document.Status.REJECTED, rejection_reason="Illegible scan"
        )

        out = onboarding_payload(
            user=merchant_user, application=application, merchant=application.merchant
        )
        doc = next(d for d in out["documents"] if d["slotId"] == "moa")
        assert doc["reviewStatus"] == "rejected"
        assert doc["rejectionReason"] == "Illegible scan"
