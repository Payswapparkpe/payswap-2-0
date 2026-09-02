"""Risk scoring and data-match analysis for staff review."""

import pytest

from merchants.models import Merchant
from merchants.privacy import encrypt_step_data
from merchants.review import application_review_context
from merchants.scoring import (
    band_from_score,
    build_match_rows,
    compute_review_scores,
    risk_status_from_score,
    update_merchant_risk_status,
)
from merchants.services import MerchantOnboardingService
from verification.models import VerificationRecord


@pytest.mark.django_db
class TestScoringEngine:
    def test_name_match_row_flags_mismatch(self, submitted_application):
        merchant = submitted_application.merchant
        record = VerificationRecord.objects.create(
            merchant=merchant,
            requested_by=merchant.owner,
            public_id="VRF-SCORE-1",
            verification_id="pan-score-1",
            verification_type=VerificationRecord.Type.PAN,
            status=VerificationRecord.Status.VERIFIED,
            verified_name="Totally Different Name",
        )
        record.set_document("ABCDE1234F", "••••••234F")
        record.save()

        rows = build_match_rows(
            merchant=merchant,
            application=submitted_application,
            records=[record],
        )
        name_rows = [row for row in rows if row["field"] == "Registered name"]
        assert name_rows
        assert name_rows[0]["status"] == "mismatch"

    def test_identifier_match_when_equal(self, submitted_application):
        merchant = submitted_application.merchant
        record = VerificationRecord.objects.create(
            merchant=merchant,
            requested_by=merchant.owner,
            public_id="VRF-SCORE-2",
            verification_id="pan-score-2",
            verification_type=VerificationRecord.Type.PAN,
            status=VerificationRecord.Status.VERIFIED,
            verified_name="Acme Private Limited",
        )
        record.set_document("ABCDE1234F", "••••••234F")
        record.set_provider_response({"registered_name": "Acme Private Limited", "pan_status": "VALID"})
        record.save()

        rows = build_match_rows(
            merchant=merchant,
            application=submitted_application,
            records=[record],
        )
        pan_rows = [row for row in rows if row["field"] == "PAN number"]
        assert pan_rows and pan_rows[0]["status"] == "match"

    def test_band_thresholds(self):
        assert band_from_score(85) == "Low"
        assert band_from_score(65) == "Medium"
        assert band_from_score(30) == "High"
        assert risk_status_from_score(85) == Merchant.RiskStatus.CLEAR
        assert risk_status_from_score(65) == Merchant.RiskStatus.REVIEW
        assert risk_status_from_score(30) == Merchant.RiskStatus.HIGH

    def test_update_merchant_risk_status_persists(self, submitted_application):
        merchant = submitted_application.merchant
        merchant.risk_status = Merchant.RiskStatus.CLEAR
        merchant.save(update_fields=["risk_status"])

        update_merchant_risk_status(merchant, application=submitted_application)

        merchant.refresh_from_db()
        assert merchant.risk_status in {
            Merchant.RiskStatus.CLEAR,
            Merchant.RiskStatus.REVIEW,
            Merchant.RiskStatus.HIGH,
        }

    def test_compute_review_scores_returns_match_rows(self, submitted_application):
        scores = compute_review_scores(
            merchant=submitted_application.merchant,
            application=submitted_application,
            records=[],
        )
        assert "kyc" in scores
        assert "kyb" in scores
        assert "match_rows" in scores
        assert "overall_score" in scores


@pytest.mark.django_db
class TestIndividualIdentityMapping:
    def test_owner_kyc_pan_surfaces_in_identity_section(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="INDIVIDUAL")
        step = application.steps.get(key="business")
        data = {
            "legal_name": "SANDEEP KUMAR",
            "brand_name": "SANDEEP KUMAR",
            "udyam_number": "UDYAM-RJ-16-0003808",
            "no_gstin": True,
        }
        step.data = encrypt_step_data(data)
        step.save(update_fields=["data"])
        owners = application.steps.get(key="owners")
        owners.data = encrypt_step_data(
            {
                "owner_name": "SANDEEP KUMAR",
                "owner_kyc": {
                    "name": "SANDEEP KUMAR",
                    "pan": "ABCPK1234D",
                    "dob": "1990-01-15",
                    "verified": True,
                    "path": "digilocker",
                },
            }
        )
        owners.save(update_fields=["data"])

        context = application_review_context(application, unmasked=True)
        identity = next(s for s in context["sections"] if s["id"] == "identity")
        pan_row = next(row for row in identity["rows"] if row["label"] == "PAN")

        assert pan_row["value"] == "ABCPK1234D"
        assert pan_row["missing"] is False


@pytest.mark.django_db
class TestUnmaskedStaffReview:
    def test_unmasked_context_shows_full_pan(self, submitted_application):
        context = application_review_context(submitted_application, unmasked=True)
        flat = {row["label"]: row["value"] for s in context["sections"] for row in s["rows"]}

        assert flat["PAN"] == "ABCDE1234F"

    def test_admin_page_logs_pii_reveal_and_shows_scores(self, client, admin_user, submitted_application):
        from audit.models import AuditEvent

        client.force_login(admin_user)
        response = client.get(f"/administration/merchants/{submitted_application.merchant.public_id}/")
        html = response.content.decode()

        assert response.status_code == 200
        assert "KYC score" in html
        assert "Data match analysis" in html
        assert AuditEvent.objects.filter(
            action="merchant.pii_reveal",
            resource_id=submitted_application.merchant.public_id,
        ).exists()

    def test_verification_tab_shows_provider_json_when_unmasked(self, client, admin_user, submitted_application):
        record = VerificationRecord.objects.create(
            merchant=submitted_application.merchant,
            requested_by=submitted_application.merchant.owner,
            public_id="VER-JSON-1",
            verification_id="ver-json-1",
            verification_type=VerificationRecord.Type.GSTIN,
            status=VerificationRecord.Status.VERIFIED,
        )
        record.set_provider_response({"gstin": "27ABCDE1234F1Z5", "legal_name_of_business": "Acme Private Limited"})
        record.save()

        client.force_login(admin_user)
        html = client.get(
            f"/administration/merchants/{submitted_application.merchant.public_id}/?tab=verification"
        ).content.decode()

        assert "Full provider API response" in html
        assert "27ABCDE1234F1Z5" in html


@pytest.mark.django_db
class TestUboKycVerifiedRoundTrip:
    def test_registry_director_kyc_carried_to_ubo_fallback(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        from api.serializers import onboarding_payload

        business = application.steps.get(key="business")
        business.data = encrypt_step_data(
            {
                "legal_name": "Acme Private Limited",
                "registry_directors": [
                    {
                        "name": "Sandeep Kumar",
                        "din": "01234567",
                        "designation": "Director",
                        "kycVerified": True,
                    }
                ],
                "ubos": [],
            }
        )
        business.save(update_fields=["data"])

        payload = onboarding_payload(
            user=application.merchant.owner,
            application=application,
            merchant=application.merchant,
        )
        assert payload["ubos"]
        assert payload["ubos"][0]["kycVerified"] is True
