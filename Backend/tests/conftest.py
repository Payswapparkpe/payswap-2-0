import pytest
from django.contrib.auth import get_user_model

from access.models import Department
from access.policy import Policy
from access.seeds import seed_access_control


@pytest.fixture
def user_model():
    return get_user_model()


@pytest.fixture
def access_seed(db):
    seed_access_control()


def _make_user(user_model, *, email, user_type, password="CorrectHorse9!", **extra):
    return user_model.objects.create_user(
        email=email,
        password=password,
        user_type=user_type,
        **extra,
    )


@pytest.fixture
def admin_user(user_model, access_seed):
    user = _make_user(user_model, email="admin@payswap.test", user_type="ADMIN", is_staff=True)
    Policy.grant_role(user, "platform_admin")
    return user


@pytest.fixture
def kyc_user(user_model, access_seed):
    dept = Department.objects.get(slug="kyc")
    user = _make_user(
        user_model,
        email="kyc@payswap.test",
        user_type="EMPLOYEE",
        department=dept,
        mfa_enforced=True,
    )
    Policy.grant_role(user, "kyc")
    return user


@pytest.fixture
def operations_user(user_model, access_seed):
    dept = Department.objects.get(slug="operations")
    user = _make_user(
        user_model,
        email="ops@payswap.test",
        user_type="EMPLOYEE",
        department=dept,
        mfa_enforced=True,
    )
    Policy.grant_role(user, "operations")
    return user


@pytest.fixture
def merchant_user(user_model, access_seed):
    user = _make_user(user_model, email="merchant@payswap.test", user_type="MERCHANT")
    Policy.grant_role(user, "merchant")
    return user


@pytest.fixture
def other_merchant_user(user_model, access_seed):
    user = _make_user(user_model, email="other-merchant@payswap.test", user_type="MERCHANT")
    Policy.grant_role(user, "merchant")
    return user


def _submitted_person(name, pan):
    return {
        "name": name,
        "pan": pan,
        "dob": "1985-04-02",
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
    }


@pytest.fixture
def submitted_application(merchant_user):
    from api.serializers import onboarding_step_data_from_angular
    from merchants.services import MerchantOnboardingService

    application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
    payload = {
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
            "registryDirectors": [
                {"name": "Sandeep Kumar", "din": "01234567", "designation": "Director"}
            ],
        },
        "signatory": _submitted_person("Sandeep Kumar", "ABCDE1234F"),
        "signatoryIsOwner": False,
        "kycPersonIsAuthorisedSignatory": False,
        "ownerKyc": _submitted_person("Meera Nair", "LMNOP4321Q"),
        "authSignatoryKyc": _submitted_person("Rohit Verma", "PQRSX9876Z"),
        "bank": {
            "accountNumber": "50100012345678",
            "ifsc": "HDFC0000123",
            "holderName": "Acme Private Limited",
            "accountType": "current",
            "bankName": "HDFC Bank",
            "branch": "Fort",
            "pennyDropStatus": "matched",
        },
        "compliance": {
            "privacyPolicy": True,
            "refundPolicy": False,
            "terms": True,
            "physicalAddress": True,
            "authorisedDeclaration": True,
            "truthDeclaration": True,
            "dpdpConsent": True,
        },
    }
    for step in ("signatory", "owner", "auth_signatory", "bank", "review"):
        key, data = onboarding_step_data_from_angular(step, payload)
        MerchantOnboardingService.save_step(
            application, key=key, actor=merchant_user, data=data, source_step=step
        )
    return application
