import re

from django.core.exceptions import ValidationError

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 64
PASSWORD_HELP = (  # nosec B105 — user-facing policy text, not a credential
    f"Use {PASSWORD_MIN_LENGTH}–{PASSWORD_MAX_LENGTH} characters with at least one lowercase "
    "letter, uppercase letter, number, and special character."
)
PASSWORD_WIDGET_ATTRS = {
    "data-validate": "password",
    "minlength": str(PASSWORD_MIN_LENGTH),
    "maxlength": str(PASSWORD_MAX_LENGTH),
    "autocomplete": "new-password",
}

_LOWER = re.compile(r"[a-z]")
_UPPER = re.compile(r"[A-Z]")
_DIGIT = re.compile(r"[0-9]")
_SPECIAL = re.compile(r"[^A-Za-z0-9]")


class PayswapPasswordValidator:
    def validate(self, password, user=None):
        errors = []
        length = len(password or "")
        if length < PASSWORD_MIN_LENGTH:
            errors.append(
                ValidationError(
                    "Password is too short.",
                    code="password_too_short",
                )
            )
        elif length > PASSWORD_MAX_LENGTH:
            errors.append(
                ValidationError(
                    "Password is too long.",
                    code="password_too_long",
                )
            )
        if (
            not _LOWER.search(password or "")
            or not _UPPER.search(password or "")
            or not _DIGIT.search(password or "")
            or not _SPECIAL.search(password or "")
        ):
            errors.append(
                ValidationError(
                    "Password does not meet the requirements.",
                    code="password_complexity",
                )
            )
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return PASSWORD_HELP
