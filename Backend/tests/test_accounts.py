import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError


@pytest.mark.django_db
class TestUserModel:
    def test_email_is_username(self):
        User = get_user_model()
        user = User.objects.create_user(
            email="rajesh@business.test",
            password="CorrectHorse9!",
            user_type="MERCHANT",
        )
        assert user.get_username() == "rajesh@business.test"
        assert user.email == "rajesh@business.test"

    def test_user_type_is_required(self):
        User = get_user_model()
        with pytest.raises(ValueError):
            User.objects.create_user(email="a@b.test", password="CorrectHorse9!")

    def test_email_must_be_unique(self):
        User = get_user_model()
        User.objects.create_user(
            email="dup@business.test",
            password="CorrectHorse9!",
            user_type="MERCHANT",
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email="dup@business.test",
                password="CorrectHorse9!",
                user_type="ADMIN",
            )

    def test_password_is_hashed(self):
        User = get_user_model()
        user = User.objects.create_user(
            email="hash@business.test",
            password="CorrectHorse9!",
            user_type="ADMIN",
        )
        assert user.password != "CorrectHorse9!"
        assert user.check_password("CorrectHorse9!")

    def test_public_id_assigned_on_create(self):
        User = get_user_model()
        user = User.objects.create_user(
            email="public@business.test",
            password="CorrectHorse9!",
            user_type="MERCHANT",
        )
        assert user.public_id.startswith("PSU-")

    def test_display_name_and_initials(self):
        User = get_user_model()
        named = User.objects.create_user(
            email="named@business.test",
            password="CorrectHorse9!",
            user_type="MERCHANT",
            name="Rajesh Kumar",
        )
        unnamed = User.objects.create_user(
            email="priya.sharma@business.test",
            password="CorrectHorse9!",
            user_type="EMPLOYEE",
        )
        assert named.display_name == "Rajesh Kumar"
        assert named.initials == "RK"
        assert unnamed.display_name == "Priya Sharma"
        assert unnamed.initials == "P"
