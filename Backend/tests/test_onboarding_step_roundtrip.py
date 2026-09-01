"""Angular wizard <-> Django step-data round-trip.

The wizard PUTs its whole application object on every save, so anything the
mapper drops is silently lost and anything `onboarding_payload` hardcodes
overwrites the merchant's real answer on the next reload.
"""

import pytest

from api.serializers import onboarding_payload, onboarding_step_data_from_angular
from merchants.models import Merchant
from merchants.privacy import decrypt_step_data
from merchants.services import MerchantOnboardingService


def _save(application, actor, step, payload):
    key, data = onboarding_step_data_from_angular(step, payload)
    return MerchantOnboardingService.save_step(application, key=key, actor=actor, data=data)


def _person(name, pan, **extra):
    return {
        "name": name,
        "pan": pan,
        "dob": "1990-01-01",
        "mobile": "9876543210",
        "path": "digilocker",
        "verified": True,
        "address": {
            "line1": "12 MG Road",
            "line2": "",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pin": "400001",
        },
        "docs": [],
        **extra,
    }


def _corporate_payload():
    return {
        "profile": {
            "legalName": "Acme Private Limited",
            "brandName": "Acme",
            "entityType": "private_limited",
            "category": "retail",
            "gstin": "27ABCDE1234F1Z5",
        },
        "identity": {
            "pan": "ABCDE1234F",
            "cin": "U74999MH2018PTC123456",
            "registeredAddress": {
                "line1": "12 MG Road",
                "line2": "",
                "city": "Mumbai",
                "state": "Maharashtra",
                "pin": "400001",
            },
        },
        "signatory": _person("Sandeep Kumar", "ABCDE1234F"),
    }


@pytest.fixture
def application(merchant_user):
    return MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")


class TestStepMapper:
    def test_auth_signatory_step_no_longer_raises(self):
        """Previously every non-signatory account opener hit HTTP 400 on save."""
        key, data = onboarding_step_data_from_angular(
            "auth_signatory",
            {
                "signatory": _person("Sandeep Kumar", "ABCDE1234F"),
                "authSignatoryKyc": _person("Rohit Verma", "PQRSX9876Z"),
            },
        )
        assert key == "owners"
        assert data["auth_signatory_kyc"]["name"] == "Rohit Verma"
        assert data["auth_signatory_kyc"]["pan"] == "PQRSX9876Z"
        assert data["authorized_signatory"] == "Rohit Verma"

    def test_owner_step_reads_owner_kyc_not_signatory(self):
        """The owner step used to persist payload['signatory'], overwriting the opener."""
        _key, data = onboarding_step_data_from_angular(
            "owner",
            {
                "signatory": _person("Sandeep Kumar", "ABCDE1234F"),
                "ownerKyc": _person("Meera Nair", "LMNOP4321Q"),
            },
        )
        assert data["owner_kyc"]["name"] == "Meera Nair"
        assert data["owner_name"] == "Meera Nair"

    def test_unknown_step_still_rejected(self):
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            onboarding_step_data_from_angular("not_a_step", {})


@pytest.mark.django_db
class TestRoundTrip:
    def test_signatory_owner_and_auth_signatory_coexist(self, application, merchant_user):
        payload = _corporate_payload()
        payload["signatoryIsOwner"] = False
        payload["kycPersonIsAuthorisedSignatory"] = False
        _save(application, merchant_user, "signatory", payload)
        _save(application, merchant_user, "owner", {**payload, "ownerKyc": _person("Meera Nair", "LMNOP4321Q")})
        _save(
            application,
            merchant_user,
            "auth_signatory",
            {**payload, "authSignatoryKyc": _person("Rohit Verma", "PQRSX9876Z")},
        )

        out = onboarding_payload(
            user=merchant_user, application=application, merchant=application.merchant
        )
        assert out["signatory"]["name"] == "Sandeep Kumar"
        assert out["ownerKyc"]["name"] == "Meera Nair"
        assert out["authSignatoryKyc"]["name"] == "Rohit Verma"

    def test_branching_flags_survive_reload(self, application, merchant_user):
        payload = _corporate_payload()
        payload["signatoryIsOwner"] = False
        payload["kycPersonIsAuthorisedSignatory"] = False
        _save(application, merchant_user, "signatory", payload)

        out = onboarding_payload(
            user=merchant_user, application=application, merchant=application.merchant
        )
        assert out["signatoryIsOwner"] is False
        assert out["kycPersonIsAuthorisedSignatory"] is False

    def test_unanswered_branching_flag_is_null_not_true(self, application, merchant_user):
        _save(application, merchant_user, "signatory", _corporate_payload())

        out = onboarding_payload(
            user=merchant_user, application=application, merchant=application.merchant
        )
        assert out["signatoryIsOwner"] is None
        assert out["kycPersonIsAuthorisedSignatory"] is None

    def test_registry_checks_survive_reload(self, application, merchant_user):
        payload = _corporate_payload()
        payload["identity"]["panCheck"] = {
            "verificationId": "ver_pan_1",
            "referenceId": 4242,
            "status": "VALID",
            "registeredName": "ACME PRIVATE LIMITED",
        }
        payload["identity"]["cinCheck"] = {
            "verificationId": "ver_cin_1",
            "referenceId": 77,
            "status": "VALID",
            "registeredName": "ACME PRIVATE LIMITED",
        }
        _save(application, merchant_user, "identity", payload)

        out = onboarding_payload(
            user=merchant_user, application=application, merchant=application.merchant
        )
        assert out["identity"]["panCheck"]["referenceId"] == 4242
        assert out["identity"]["cinCheck"]["status"] == "VALID"
        assert out["identity"]["gstinCheck"] is None

    def test_later_save_without_check_does_not_clear_it(self, application, merchant_user):
        payload = _corporate_payload()
        payload["identity"]["panCheck"] = {
            "verificationId": "ver_pan_1",
            "referenceId": 4242,
            "status": "VALID",
            "registeredName": "ACME PRIVATE LIMITED",
        }
        _save(application, merchant_user, "identity", payload)
        _save(application, merchant_user, "identity", _corporate_payload())

        out = onboarding_payload(
            user=merchant_user, application=application, merchant=application.merchant
        )
        assert out["identity"]["panCheck"]["referenceId"] == 4242

    def test_business_save_keeps_structured_person_records(self, application, merchant_user):
        """_mirror_owners_step used to replace the whole owners payload."""
        payload = _corporate_payload()
        _save(application, merchant_user, "owner", {**payload, "ownerKyc": _person("Meera Nair", "LMNOP4321Q")})
        _save(application, merchant_user, "signatory", payload)

        owners = decrypt_step_data(application.steps.get(key="owners").data)
        assert owners["owner_kyc"]["name"] == "Meera Nair"

    def test_compliance_answers_are_not_fabricated(self, application, merchant_user):
        _save(
            application,
            merchant_user,
            "review",
            {
                "compliance": {
                    "privacyPolicy": True,
                    "refundPolicy": False,
                    "terms": True,
                    "physicalAddress": True,
                    "authorisedDeclaration": False,
                    "truthDeclaration": True,
                    "dpdpConsent": True,
                }
            },
        )
        out = onboarding_payload(
            user=merchant_user, application=application, merchant=application.merchant
        )
        assert out["compliance"]["refundPolicy"] is False
        assert out["compliance"]["authorisedDeclaration"] is False
        assert out["compliance"]["privacyPolicy"] is True

    def test_registry_members_survive_reload(self, application, merchant_user):
        payload = _corporate_payload()
        payload["registryMembers"] = [{"name": "Partner One", "designation": "Partner", "din": ""}]
        _save(application, merchant_user, "identity", payload)

        out = onboarding_payload(
            user=merchant_user, application=application, merchant=application.merchant
        )
        assert out["registryMembers"][0]["name"] == "Partner One"

    def test_nested_person_pan_is_encrypted_at_rest(self, application, merchant_user):
        _save(
            application,
            merchant_user,
            "owner",
            {**_corporate_payload(), "ownerKyc": _person("Meera Nair", "LMNOP4321Q")},
        )
        raw = application.steps.get(key="owners").data
        assert "LMNOP4321Q" not in str(raw)
        assert decrypt_step_data(raw)["owner_kyc"]["pan"] == "LMNOP4321Q"
