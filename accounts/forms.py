
from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction

from .models import CustomerProfile


User = get_user_model()


def apply_form_control_classes(form: forms.BaseForm) -> None:
    """Apply consistent classes and accessible error/help relationships."""

    for name, field in form.fields.items():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.setdefault("class", "form-check-input")
        else:
            field.widget.attrs.setdefault("class", "form-control")
        element_id = field.widget.attrs.get("id", f"id_{name}")
        field.widget.attrs.setdefault("id", element_id)
        field.widget.attrs["aria-describedby"] = f"{element_id}_help {element_id}_error"
        if form.is_bound and name in form.errors:
            field.widget.attrs["aria-invalid"] = "true"


class SignUpForm(UserCreationForm):
    """Public registration form; every new account starts as a normal customer."""

    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=30, required=False)
    privacy_consent = forms.BooleanField(
        required=True,
        label="I agree that Popadoo may store these details for account and booking use.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "password1",
            "password2",
            "privacy_consent",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Used to sign in. It must be unique."
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["phone"].widget.attrs["autocomplete"] = "tel"
        apply_form_control_classes(self)

    # This validation step checks and prepares the email value before it is used.
    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already uses this email address.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        if commit:
            user.save()
            profile, _ = CustomerProfile.objects.get_or_create(user=user)
            profile.phone = self.cleaned_data.get("phone", "").strip()
            profile.save(update_fields=["phone", "updated_at"])
        return user


class PopadooAuthenticationForm(AuthenticationForm):
    """Django authentication with project styling and safe generic errors."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"
        apply_form_control_classes(self)


class ProfileForm(forms.ModelForm):
    """Edit the account identity and saved booking-autofill fields together."""

    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = CustomerProfile
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone",
            "default_address",
            "default_postal_code",
            "preferred_language",
        )
        widgets = {
            "default_address": forms.TextInput(attrs={"autocomplete": "street-address"}),
            "default_postal_code": forms.TextInput(attrs={"autocomplete": "postal-code"}),
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email
        apply_form_control_classes(self)

    # This validation step checks and prepares the email value before it is used.
    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Another account already uses this email address.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=False)
        self.user.first_name = self.cleaned_data["first_name"].strip()
        self.user.last_name = self.cleaned_data["last_name"].strip()
        self.user.email = self.cleaned_data["email"]
        if commit:
            self.user.save(update_fields=["first_name", "last_name", "email"])
            profile.save()
        return profile
