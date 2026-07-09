from __future__ import annotations

import re
from datetime import date

from django import forms
from django.utils import timezone

from .models import AddonExperience, GuestPriceTier, PartyPackage
from .services import SafePaymentResult


def _apply_accessible_attributes(form: forms.BaseForm) -> None:
    """Connect every control to predictable help and error containers."""

    for field_name, field in form.fields.items():
        element_id = field.widget.attrs.get("id", f"id_{field_name}")
        field.widget.attrs.setdefault("id", element_id)
        field.widget.attrs["aria-describedby"] = (
            f"{element_id}_help {element_id}_error"
        )

    if form.is_bound:
        for field_name in form.errors:
            if field_name in form.fields:
                form.fields[field_name].widget.attrs["aria-invalid"] = "true"


class PackageOptionsForm(forms.Form):
    """Step one: validate the guest bracket and optional experiences."""

    guest_tier = forms.ModelChoiceField(
        queryset=GuestPriceTier.objects.none(),
        empty_label=None,
        widget=forms.RadioSelect,
        label="Number of children",
    )
    addons = forms.ModelMultipleChoiceField(
        queryset=AddonExperience.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Optional experiences",
    )

    def __init__(self, *args, package: PartyPackage, **kwargs):
        self.package = package
        super().__init__(*args, **kwargs)
        self.fields["guest_tier"].queryset = package.guest_price_tiers.filter(
            is_active=True
        ).order_by("display_order", "min_guests")
        self.fields["addons"].queryset = AddonExperience.objects.filter(
            is_active=True
        ).order_by("display_order", "name")
        _apply_accessible_attributes(self)

    def clean_guest_tier(self) -> GuestPriceTier:
        tier = self.cleaned_data["guest_tier"]
        if tier.package_id != self.package.pk or not tier.is_active:
            raise forms.ValidationError("Choose an available guest option.")
        return tier


class PartyDetailsForm(forms.Form):
    """Step two: collect customer and event details without saving yet."""

    contact_name = forms.CharField(
        max_length=120,
        label="Parent or guardian name",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "name",
                "placeholder": "Full name",
            }
        ),
    )
    contact_email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "email",
                "placeholder": "name@example.com",
            }
        ),
    )
    contact_phone = forms.CharField(
        max_length=30,
        label="Phone number",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "type": "tel",
                "autocomplete": "tel",
                "placeholder": "+30 69…",
            }
        ),
    )
    event_date = forms.DateField(
        label="Preferred event date",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        help_text="Choose today or a future date. Availability is confirmed later.",
    )
    event_time = forms.TimeField(
        required=False,
        label="Preferred start time",
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
    )
    guest_count = forms.IntegerField(
        min_value=1,
        max_value=200,
        label="Expected number of children",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "inputmode": "numeric"}
        ),
    )
    event_address = forms.CharField(
        max_length=240,
        label="Event address",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "street-address",
                "placeholder": "Street, number, area",
            }
        ),
    )
    postal_code = forms.CharField(
        max_length=10,
        label="Postal code",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "postal-code",
                "inputmode": "numeric",
                "placeholder": "153 42",
            }
        ),
    )
    notes = forms.CharField(
        required=False,
        max_length=1500,
        label="Extra details",
        help_text="Theme, age range, venue restrictions, or accessibility needs.",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Tell us what would make the experience feel right.",
            }
        ),
    )

    def __init__(self, *args, guest_tier: GuestPriceTier, **kwargs):
        self.guest_tier = guest_tier
        super().__init__(*args, **kwargs)
        self.fields["event_date"].widget.attrs["min"] = date.today().isoformat()
        self.fields["guest_count"].widget.attrs.update(
            {
                "min": str(guest_tier.min_guests),
                "max": str(guest_tier.max_guests),
            }
        )
        self.fields["guest_count"].help_text = (
            f"Enter a number from {guest_tier.min_guests} to "
            f"{guest_tier.max_guests} for the selected bracket."
        )
        _apply_accessible_attributes(self)

    def clean_contact_phone(self) -> str:
        phone = self.cleaned_data["contact_phone"].strip()
        digits = re.sub(r"\D", "", phone)
        if not re.fullmatch(r"\+?[0-9\s().-]+", phone) or not 7 <= len(digits) <= 15:
            raise forms.ValidationError("Enter a valid phone number.")
        return phone

    def clean_event_date(self):
        event_date = self.cleaned_data["event_date"]
        if event_date < timezone.localdate():
            raise forms.ValidationError("Choose today or a future date.")
        return event_date

    def clean_guest_count(self) -> int:
        guest_count = self.cleaned_data["guest_count"]
        if not self.guest_tier.contains_guest_count(guest_count):
            raise forms.ValidationError(
                f"This option covers {self.guest_tier.min_guests}–"
                f"{self.guest_tier.max_guests} children."
            )
        return guest_count

    def clean_postal_code(self) -> str:
        postal_code = self.cleaned_data["postal_code"].strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\s-]{2,9}", postal_code):
            raise forms.ValidationError("Enter a valid postal code.")
        return postal_code


class SimulatedPaymentForm(forms.Form):
    """Step three: validate test card details and discard sensitive values."""

    cardholder_name = forms.CharField(
        max_length=120,
        label="Name on test card",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "off",
            }
        ),
    )
    card_number = forms.CharField(
        min_length=13,
        max_length=23,
        label="Test card number",
        help_text="Simulation only. You may use 4242 4242 4242 4242.",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "off",
                "inputmode": "numeric",
                "data-card-number": "",
                "placeholder": "4242 4242 4242 4242",
            }
        ),
    )
    expiry_month = forms.ChoiceField(
        label="Expiry month",
        choices=[(f"{month:02d}", f"{month:02d}") for month in range(1, 13)],
        widget=forms.Select(attrs={"class": "form-control", "autocomplete": "cc-exp-month"}),
    )
    expiry_year = forms.ChoiceField(
        label="Expiry year",
        choices=(),
        widget=forms.Select(attrs={"class": "form-control", "autocomplete": "cc-exp-year"}),
    )
    security_code = forms.CharField(
        min_length=3,
        max_length=4,
        label="Security code",
        widget=forms.PasswordInput(
            render_value=False,
            attrs={
                "class": "form-control",
                "autocomplete": "off",
                "inputmode": "numeric",
                "placeholder": "123",
            },
        ),
    )
    billing_postal_code = forms.CharField(
        max_length=10,
        label="Billing postal code",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "postal-code",
                "inputmode": "numeric",
            }
        ),
    )
    simulation_consent = forms.BooleanField(
        required=True,
        label=(
            "I understand this is a simulated checkout and no payment or "
            "financial transaction will take place."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = timezone.localdate().year
        self.fields["expiry_year"].choices = [
            (str(year), str(year)) for year in range(current_year, current_year + 11)
        ]
        _apply_accessible_attributes(self)

    @staticmethod
    def _passes_luhn(number: str) -> bool:
        digits = [int(character) for character in number]
        checksum = 0
        parity = len(digits) % 2
        for index, digit in enumerate(digits):
            if index % 2 == parity:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit
        return checksum % 10 == 0

    @staticmethod
    def _detect_brand(number: str) -> str:
        if number.startswith("4"):
            return "Visa"
        if len(number) >= 2 and 51 <= int(number[:2]) <= 55:
            return "Mastercard"
        if number.startswith(("34", "37")):
            return "American Express"
        return "Test card"

    def clean_card_number(self) -> str:
        number = re.sub(r"\D", "", self.cleaned_data["card_number"])
        approved_test_numbers = {
            "4242424242424242",
            "5555555555554444",
            "378282246310005",
        }
        if number not in approved_test_numbers or not self._passes_luhn(number):
            raise forms.ValidationError(
                "Use an approved demo number such as 4242 4242 4242 4242."
            )
        return number

    def clean_security_code(self) -> str:
        code = self.cleaned_data["security_code"].strip()
        if not re.fullmatch(r"\d{3,4}", code):
            raise forms.ValidationError("Enter a 3 or 4 digit security code.")
        return code

    def clean_billing_postal_code(self) -> str:
        postal_code = self.cleaned_data["billing_postal_code"].strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\s-]{2,9}", postal_code):
            raise forms.ValidationError("Enter a valid billing postal code.")
        return postal_code

    def clean(self):
        cleaned_data = super().clean()
        month = cleaned_data.get("expiry_month")
        year = cleaned_data.get("expiry_year")
        if month and year:
            today = timezone.localdate()
            if (int(year), int(month)) < (today.year, today.month):
                self.add_error("expiry_month", "Choose a future expiry date.")
        return cleaned_data

    def safe_payment_result(self) -> SafePaymentResult:
        """Return only metadata safe to store after the form is valid."""

        number = self.cleaned_data["card_number"]
        return SafePaymentResult(
            card_brand=self._detect_brand(number),
            card_last_four=number[-4:],
        )
