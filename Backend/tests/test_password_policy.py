import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.password_policy import PayswapPasswordValidator


def _messages(password):
    try:
        validate_password(password)
    except ValidationError as exc:
        return exc.messages
    return []


@pytest.mark.django_db
class TestPasswordPolicy:
    def test_accepts_mixed_10_to_20_characters(self):
        validate_password("Abcd1234!@")
        validate_password("CorrectHorse9!")
        validate_password("Aa1!" + "x" * 12 + "Z")
        validate_password("Aa1!" + "x" * 40 + "Z")

    def test_rejects_too_short_or_too_long(self):
        assert any("too short" in msg for msg in _messages("Aa1!aa1!"))
        assert any("too long" in msg for msg in _messages("Aa1!" + "x" * 70))

    def test_requires_each_character_class(self):
        assert any("does not meet the requirements" in msg for msg in _messages("abcd1234!@"))
        assert any("does not meet the requirements" in msg for msg in _messages("ABCD1234!@"))
        assert any("does not meet the requirements" in msg for msg in _messages("Abcdefgh!@"))
        assert any("does not meet the requirements" in msg for msg in _messages("Abcd1234aa"))

    def test_help_text_describes_the_rule(self):
        help_text = PayswapPasswordValidator().get_help_text()
        assert "10–64" in help_text
        assert "lowercase" in help_text
        assert "uppercase" in help_text
        assert "number" in help_text
        assert "special" in help_text

    def test_register_rejects_a_weak_password(self, client):
        response = client.post(
            "/merchant/register/",
            {
                "step": "details",
                "action": "continue",
                "name": "Weak Password",
                "email": "weak.password@payswap.test",
                "mobile": "9876543299",
                "address": "12 MG Road, Bengaluru",
                "pincode": "560001",
                "entity_type": "INDIVIDUAL",
                "password": "password",
                "confirm_password": "password",
            },
        )
        assert response.status_code == 400
        html = response.content.decode()
        assert "too short" in html or "does not meet the requirements" in html

    def test_register_form_shows_length_limits(self, client):
        html = client.get("/merchant/register/").content.decode()
        assert 'minlength="10"' in html
        assert 'maxlength="64"' in html
