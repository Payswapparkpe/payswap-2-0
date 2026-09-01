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
