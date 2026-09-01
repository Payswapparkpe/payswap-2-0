import pytest

from access.models import Department
from access.policy import Policy
from accounts.models import User


@pytest.mark.django_db
class TestStaffMfaRequired:
    def test_kyc_without_mfa_is_sent_to_setup(self, client, access_seed, user_model):
        dept = Department.objects.get(slug="kyc")
        user = user_model.objects.create_user(
            email="kyc-nomfa@payswap.test",
            password="CorrectHorse9!",
            user_type=User.UserType.EMPLOYEE,
            department=dept,
            mfa_enforced=False,
        )
        Policy.grant_role(user, "kyc")
        client.force_login(user)
        response = client.get("/employee/")
        assert response.status_code == 302
        assert response.url == "/mfa/setup/"

    def test_enrolled_kyc_reaches_employee_home(self, client, kyc_user):
        client.force_login(kyc_user)
        response = client.get("/employee/")
        assert response.status_code == 200
