from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.password_policy import PASSWORD_WIDGET_ATTRS
from merchants.models import Merchant

User = get_user_model()


class PortalLoginForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        error_messages={"invalid": "Enter a valid email.", "required": "This field is required."},
        widget=forms.EmailInput(
            attrs={
                "data-validate": "email",
                "autocomplete": "username",
                "inputmode": "email",
                "placeholder": "Enter your email",
            }
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "data-validate": "required",
                "autocomplete": "current-password",
                "placeholder": "Enter your password",
            }
        ),
        label="Password",
    )

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        password = cleaned.get("password")
        if not email or not password:
            return cleaned
        user = authenticate(username=email, password=password)
        if user is None or not user.is_active:
            # Identical message for bad credentials and suspended accounts:
            # differing responses would disclose account state to anyone.
            raise forms.ValidationError("The email or password is incorrect.")
        cleaned["user"] = user
        return cleaned


class MerchantRegisterForm(forms.Form):
    name = forms.CharField(
        label="Full name",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "data-validate": "required",
                "autocomplete": "name",
                "placeholder": "Enter your full name",
            }
        ),
    )
    email = forms.EmailField(
        label="Work email",
        error_messages={"invalid": "Enter a valid email.", "required": "This field is required."},
        widget=forms.EmailInput(
            attrs={
                "data-validate": "email",
                "autocomplete": "email",
                "placeholder": "Enter your work email",
            }
        ),
    )
    mobile = forms.RegexField(
        label="Mobile number",
        regex=r"^[6-9]\d{9}$",
        error_messages={"invalid": "Enter a valid mobile number.", "required": "This field is required."},
        widget=forms.TextInput(
            attrs={
                "data-validate": "mobile",
                "inputmode": "numeric",
                "maxlength": "10",
                "autocomplete": "tel",
                "placeholder": "Enter your mobile number",
            }
        ),
    )
    address = forms.CharField(
        label="Address",
        min_length=8,
        max_length=240,
        widget=forms.TextInput(
            attrs={
                "data-validate": "required",
                "autocomplete": "street-address",
                "placeholder": "Enter your address",
            }
        ),
    )
    pincode = forms.RegexField(
        label="PIN code",
        regex=r"^[1-9][0-9]{5}$",
        error_messages={"invalid": "Enter a valid PIN code.", "required": "This field is required."},
        widget=forms.TextInput(
            attrs={
                "data-validate": "pincode",
                "inputmode": "numeric",
                "maxlength": "6",
                "autocomplete": "postal-code",
                "placeholder": "Enter PIN code",
            }
        ),
    )
    entity_type = forms.ChoiceField(
        label="Business type",
        choices=Merchant.EntityType.choices,
        initial=Merchant.EntityType.INDIVIDUAL,
        widget=forms.Select(
            attrs={
                "data-validate": "required",
            }
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={**PASSWORD_WIDGET_ATTRS, "placeholder": "Enter a password"}),
        label="Password",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "data-validate": "confirm-password",
                "autocomplete": "new-password",
                "placeholder": "Re-enter your password",
            }
        ),
        label="Confirm password",
    )
    accept_terms = forms.BooleanField(
        required=False,
        label="I accept the Terms and Conditions and Privacy Policy",
        error_messages={"required": "Accept the Terms and Conditions and Privacy Policy."},
        widget=forms.CheckboxInput(attrs={"data-validate": "terms", "required": True}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") and cleaned.get("password") != cleaned.get("confirm_password"):
            self.add_error("confirm_password", "The passwords do not match.")
        if cleaned.get("password"):
            try:
                validate_password(cleaned["password"])
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        error_messages={"invalid": "Enter a valid email.", "required": "This field is required."},
        widget=forms.EmailInput(
            attrs={
                "data-validate": "email",
                "autocomplete": "username",
                "inputmode": "email",
                "placeholder": "Enter your email",
            }
        ),
    )


class PasswordResetConfirmForm(forms.Form):
    password = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={**PASSWORD_WIDGET_ATTRS, "placeholder": "Enter a new password"}),
    )
    confirm_password = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(
            attrs={
                "data-validate": "confirm-password",
                "autocomplete": "new-password",
                "placeholder": "Re-enter your password",
            }
        ),
    )

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password and password != cleaned.get("confirm_password"):
            self.add_error("confirm_password", "The passwords do not match.")
        if password:
            try:
                validate_password(password)
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned
