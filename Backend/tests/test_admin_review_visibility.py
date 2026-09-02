"""A reviewer must actually see the submitted application.

Before this, the Overview tab rendered only the owner's email and the
application status, so a KYC reviewer approved corporate merchants blind.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from access.models import Permission
from access.policy import Policy
from merchants.privacy import MASK_BULLET, display_step_data, encrypt_step_data
from merchants.review import CLARIFICATION_SECTIONS, application_review_context
from merchants.services import MerchantOnboardingService
from verification.models import Document, VerificationRecord

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00"
    b"\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.django_db
class TestReviewContext:
    def test_sections_carry_the_submitted_values(self, submitted_application):
        context = application_review_context(submitted_application)
        flat = {row["label"]: row["value"] for s in context["sections"] for row in s["rows"]}

        assert flat["Legal name"] == "Acme Private Limited"
        assert flat["Entity type"] == "Private Limited Company"
        assert flat["Bank"] == "HDFC Bank"
        assert flat["IFSC"] == "HDFC0000123"
        assert flat["Penny drop"] == "Matched"
        assert flat["Refund policy published"] == "No"

    def test_identifiers_are_masked_never_raw(self, submitted_application):
        context = application_review_context(submitted_application)
        flat = {row["label"]: row["value"] for s in context["sections"] for row in s["rows"]}

        assert flat["PAN"].endswith("234F")
        assert MASK_BULLET in flat["PAN"]
        assert "ABCDE1234F" not in flat["PAN"]
        assert MASK_BULLET in flat["CIN"]

    def test_three_people_are_listed_separately(self, submitted_application):
        context = application_review_context(submitted_application)
        by_role = {person["role"]: person for person in context["people"]}

        assert by_role["Account opener / signatory"]["name"] == "Sandeep Kumar"
        assert by_role["Business owner / director"]["name"] == "Meera Nair"
        assert by_role["Authorised signatory"]["name"] == "Rohit Verma"

    def test_person_pan_is_masked_in_the_people_section(self, submitted_application):
        context = application_review_context(submitted_application)
        owner = next(p for p in context["people"] if p["role"] == "Business owner / director")
        pan = next(row["value"] for row in owner["rows"] if row["label"] == "PAN")

        assert "LMNOP4321Q" not in pan
        assert pan.endswith("321Q")

    def test_branching_answers_are_reported(self, submitted_application):
        context = application_review_context(submitted_application)

        assert context["signatory_is_owner"] is False
        assert context["kyc_person_is_authorised_signatory"] is False

    def test_directors_are_listed(self, submitted_application):
        context = application_review_context(submitted_application)

        assert context["directors"]["rows"][0]["name"] == "Sandeep Kumar"
        assert context["directors"]["rows"][0]["identifier"] == "01234567"

    def test_missing_values_are_flagged_for_the_reviewer(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        context = application_review_context(application)
        business = next(s for s in context["sections"] if s["id"] == "business")

        assert any(row["missing"] for row in business["rows"])

    def test_no_application_degrades_gracefully(self):
        assert application_review_context(None)["available"] is False


@pytest.mark.django_db
class TestAdminMerchantDetailPage:
    def _url(self, application):
        return f"/administration/merchants/{application.merchant.public_id}/"

    def test_overview_renders_application_data(self, client, admin_user, submitted_application):
        client.force_login(admin_user)
        html = client.get(self._url(submitted_application)).content.decode()

        assert "Acme Private Limited" in html
        assert "HDFC Bank" in html
        assert "Meera Nair" in html
        assert "Rohit Verma" in html

    def test_overview_masks_pan_for_view_only_staff(self, client, submitted_application, user_model, access_seed):
        from access.models import Permission, Role
        from access.policy import Policy

        role, _ = Role.objects.get_or_create(slug="audit_viewer", defaults={"name": "Audit Viewer"})
        role.permissions.set(
            Permission.objects.filter(codename__in=["portal.administration", "merchant.view"])
        )
        viewer = user_model.objects.create_user(
            email="audit@payswap.test",
            password="CorrectHorse9!",
            user_type="ADMIN",
            is_staff=True,
        )
        Policy.grant_role(viewer, "audit_viewer")
        client.force_login(viewer)
        html = client.get(self._url(submitted_application)).content.decode()

        assert "ABCDE1234F" not in html
        assert "LMNOP4321Q" not in html

    def test_verification_tab_lists_records(self, client, admin_user, submitted_application):
        VerificationRecord.objects.create(
            merchant=submitted_application.merchant,
            requested_by=submitted_application.merchant.owner,
            public_id="VER-0001",
            verification_type=VerificationRecord.Type.PAN,
            status=VerificationRecord.Status.VERIFIED,
        )
        client.force_login(admin_user)
        html = client.get(f"{self._url(submitted_application)}?tab=verification").content.decode()

        assert "VER-0001" in html
        assert "PAN" in html

    def test_documents_tab_offers_a_download(self, client, admin_user, submitted_application):
        Document.objects.create(
            merchant=submitted_application.merchant,
            public_id="DOC-0001",
            doc_type=Document.DocType.BOARD_RESOLUTION,
            slot_id="board_resolution",
            uploaded_by=submitted_application.merchant.owner,
            file=SimpleUploadedFile("bor.png", PNG, content_type="image/png"),
        )
        client.force_login(admin_user)
        html = client.get(f"{self._url(submitted_application)}?tab=documents").content.decode()

        assert "/administration/documents/DOC-0001/download/" in html
        assert "Request replacement" in html

    def test_clarification_dropdown_offers_wizard_steps(self, client, admin_user, submitted_application):
        client.force_login(admin_user)
        html = client.get(self._url(submitted_application)).content.decode()

        for key, label in CLARIFICATION_SECTIONS:
            assert f'value="{key}"' in html
            assert label in html


@pytest.mark.django_db
class TestDocumentActions:
    def _document(self, merchant):
        return Document.objects.create(
            merchant=merchant,
            public_id="DOC-RPL-01",
            doc_type=Document.DocType.MOA,
            slot_id="moa",
            uploaded_by=merchant.owner,
            status=Document.Status.UNDER_REVIEW,
            file=SimpleUploadedFile("moa.png", PNG, content_type="image/png"),
        )

    def test_request_replacement_is_wired(self, client, admin_user, submitted_application):
        document = self._document(submitted_application.merchant)
        client.force_login(admin_user)

        response = client.post(
            f"/administration/documents/{document.public_id}/",
            {"action": "request_replacement", "reason": "Scan is illegible"},
        )

        assert response.status_code == 302
        document.refresh_from_db()
        assert document.status == Document.Status.ACTION_REQUIRED
        assert document.rejection_reason == "Scan is illegible"

    def test_request_replacement_needs_a_reason(self, client, admin_user, submitted_application):
        document = self._document(submitted_application.merchant)
        client.force_login(admin_user)

        client.post(
            f"/administration/documents/{document.public_id}/",
            {"action": "request_replacement", "reason": "  "},
        )

        document.refresh_from_db()
        assert document.status == Document.Status.UNDER_REVIEW

    def test_reviewer_can_download_a_merchant_document(self, client, kyc_user, submitted_application):
        document = self._document(submitted_application.merchant)
        client.force_login(kyc_user)

        response = client.post(f"/employee/documents/{document.public_id}/download/")

        assert response.status_code == 200

    def test_other_merchant_cannot_download(
        self, client, other_merchant_user, submitted_application
    ):
        document = self._document(submitted_application.merchant)
        MerchantOnboardingService.start(other_merchant_user, entity_type="INDIVIDUAL")
        client.force_login(other_merchant_user)

        response = client.post(f"/merchant/documents/{document.public_id}/download/")

        assert response.status_code in {403, 404}


@pytest.mark.django_db
class TestEmployeeParity:
    def test_employee_page_shows_the_same_sections(self, client, kyc_user, submitted_application):
        client.force_login(kyc_user)
        html = client.get(f"/employee/queue/{submitted_application.public_id}/").content.decode()

        assert "Acme Private Limited" in html
        assert "Meera Nair" in html
        assert "HDFC Bank" in html
        assert "KYC score" in html
        assert "Data match analysis" in html

    def test_employee_clarification_matches_admin(self, client, kyc_user, submitted_application):
        client.force_login(kyc_user)
        html = client.get(f"/employee/queue/{submitted_application.public_id}/").content.decode()

        for key, label in CLARIFICATION_SECTIONS:
            assert f'value="{key}"' in html
            assert label in html


@pytest.mark.django_db
class TestSeededPermissions:
    def test_merchant_manage_is_seeded(self, access_seed):
        assert Permission.objects.filter(codename="merchant.manage").exists()

    def test_platform_admin_holds_merchant_manage(self, admin_user):
        assert Policy.has_permission(admin_user, "merchant.manage")

    def test_expire_verification_succeeds_for_admin(self, client, admin_user, submitted_application):
        record = VerificationRecord.objects.create(
            merchant=submitted_application.merchant,
            requested_by=submitted_application.merchant.owner,
            public_id="VER-EXP-01",
            verification_type=VerificationRecord.Type.PAN,
            status=VerificationRecord.Status.VERIFIED,
        )
        client.force_login(admin_user)

        response = client.post("/administration/verification/", {"record": record.public_id, "action": "expire"})

        assert response.status_code == 302
        record.refresh_from_db()
        assert record.status == VerificationRecord.Status.EXPIRED


class TestNestedMasking:
    def test_display_masks_nested_person_pan(self):
        stored = encrypt_step_data({"owner_kyc": {"name": "Meera", "pan": "LMNOP4321Q"}})
        shown = display_step_data(stored)

        assert shown["owner_kyc"]["pan"].endswith("321Q")
        assert "LMNOP4321Q" not in shown["owner_kyc"]["pan"]

    def test_display_masks_pan_inside_lists(self):
        stored = encrypt_step_data({"ubos": [{"name": "A", "pan": "AAAAA1111A"}]})
        shown = display_step_data(stored)

        assert "AAAAA1111A" not in shown["ubos"][0]["pan"]


class TestProviderPayloadDisplay:
    def test_masks_nested_provider_pan(self):
        from merchants.review import display_provider_payload

        masked = display_provider_payload({"pan": "ABCDE1234F", "status": "VALID"})

        assert "ABCDE1234F" not in masked["pan"]
        assert str(masked["pan"]).endswith("234F")
        assert masked["status"] == "VALID"

    def test_furnish_pan_record(self):
        from merchants.review import furnish_verification_record

        class Stub:
            verification_type = "PAN"
            document_masked = "••••••234F"
            verified_name = "Acme Pvt Ltd"
            verified_dob = ""
            verified_gender = ""
            verified_address = ""
            verified_city = ""
            verified_state = ""
            verified_district = ""
            verified_pincode = ""
            name_match_score = 0.92
            name_match_category = "STRONG_MATCH"
            failure_reason = ""
            requested_at = None
            completed_at = None
            expires_at = None
            reference_id = "12345"
            reused_from_id = None

            def get_provider_response(self):
                return {"pan_status": "VALID", "name_match": "EXACT_MATCH"}

            verified_data_encrypted = ""

            @property
            def display_reason(self):
                return ""

        furnished = furnish_verification_record(Stub())
        labels = {row["label"] for section in furnished["sections"] for row in section["rows"]}

        assert "PAN status" in labels
        assert furnished["match_percent"] == 92
        assert "Acme Pvt Ltd" in furnished["highlights"]


@pytest.mark.django_db
class TestAdminMerchantDetailPayloads:
    def test_overview_does_not_show_raw_payload_json(self, client, admin_user, submitted_application):
        client.force_login(admin_user)
        html = client.get(
            f"/administration/merchants/{submitted_application.merchant.public_id}/"
        ).content.decode()

        assert "Stored application payloads" not in html
        assert "api-payload-body" not in html
        assert "Acme Private Limited" in html

    def test_verification_tab_shows_furnished_summary(self, client, admin_user, submitted_application):
        record = VerificationRecord.objects.create(
            merchant=submitted_application.merchant,
            requested_by=submitted_application.merchant.owner,
            public_id="VER-PAY-01",
            verification_type=VerificationRecord.Type.PAN,
            verification_id="verify-pan-test-01",
            document_hash="abc123",
            document_masked="••••••234F",
            verified_name="Acme Private Limited",
            status=VerificationRecord.Status.VERIFIED,
        )
        record.set_provider_response({"pan": "ABCDE1234F", "pan_status": "VALID", "name_match": "EXACT_MATCH"})
        record.save()

        client.force_login(admin_user)
        html = client.get(
            f"/administration/merchants/{submitted_application.merchant.public_id}/?tab=verification"
        ).content.decode()

        assert "Registry details" in html
        assert "PAN status" in html
        assert "Full provider API response" in html
        assert "ABCDE1234F" in html
        assert "Acme Private Limited" in html
