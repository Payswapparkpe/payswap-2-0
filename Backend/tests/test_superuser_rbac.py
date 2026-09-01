import pytest

from access.policy import Policy
from accounts.models import User


@pytest.mark.django_db
class TestSuperuserRbac:
    def test_superuser_without_roles_has_no_app_permissions(self, access_seed, user_model):
        user = user_model.objects.create_superuser(
            email="root@payswap.test",
            password="CorrectHorse9!",
            user_type=User.UserType.ADMIN,
        )
        assert user.is_superuser
        assert not Policy.can(user, "order.approve")
        assert not Policy.can(user, "order.create")
        assert not Policy.has_permission(user, "merchant.review")
        assert Policy.can(user, "portal.administration")
