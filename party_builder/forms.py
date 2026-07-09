from __future__ import annotations

import re
from datetime import date

from django import forms
from django.db import transaction

from .models import AddonExperience, PartyBuild, PartyBuildAddon, PartyPackage
from .services import calculate_party_quote


class PartyBuildForm(forms.ModelForm):
    """Validate customer details and selected experiences on the server."""

    addons = forms.ModelMultipleChoiceField(
        queryset=AddonExperience.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Optional experiences",
    )
    consent = forms.BooleanField(
        required=True,
        label="I agree that Popadoo may use these details to contact me about this request.",
    )

    class Meta:
        model = PartyBuild
        fields = (
            "contact_name",
            "contact_email",
            "contact_phone",
            "event_date",
            "guest_count",
            "notes",
        )
        widgets = {
            "contact_name": forms.TextInput(
                attrs={
                    "autocomplete": "name",
                    "class": "form-control",
                    "placeholder": "Parent or guardian name",
                }
            ),
            "contact_email": forms.EmailInput(
                attrs={
                    "autocomplete": "email",
                    "class": "form-control",
                    "placeholder": "name@example.com",
                }
            ),
            "contact_phone": forms.TextInput(
                attrs={
                    "type": "tel",
                    "autocomplete": "tel",
                    "class": "form-control",
                    "placeholder": "+30 69…",
                }
            ),
            "event_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                }
            ),
            "guest_count": forms.NumberInput(
                attrs={
                    "min": "1",
                    "max": "200",
                    "inputmode": "numeric",
                    "class": "form-control",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": "5",
                    "class": "form-control",
                    "placeholder": "Theme, venue, ages, accessibility needs, or anything else we should know.",
                }
            ),
        }
        labels = {
            "contact_name": "Contact name",
            "contact_email": "Email address",
            "contact_phone": "Phone number",
            "event_date": "Preferred event date",
            "guest_count": "Expected number of children",
            "notes": "Extra details (optional)",
        }
        help_texts = {
            "event_date": "Choose a future date. Availability is confirmed after review.",
            "guest_count": "The basic package includes up to 15 children; larger groups may require an extra entertainer.",
            "notes": "Do not include sensitive medical information. We will discuss detailed requirements privately.",
        }

    def __init__(self, *args, package: PartyPackage, **kwargs):
        self.package = package
        super().__init__(*args, **kwargs)

        self.fields["addons"].queryset = AddonExperience.objects.filter(
            is_active=True
        ).order_by("display_order", "name")

        today = date.today().isoformat()
        self.fields["event_date"].widget.attrs["min"] = today

        # Link controls to help and error text for assistive technology.
        for field_name, field in self.fields.items():
            element_id = field.widget.attrs.get("id", f"id_{field_name}")
            field.widget.attrs.setdefault("id", element_id)
            field.widget.attrs["aria-describedby"] = (
                f"{element_id}_help {element_id}_error"
            )

        # Bound forms expose invalid state while preserving native validation.
        if self.is_bound:
            for field_name in self.errors:
                self.fields[field_name].widget.attrs["aria-invalid"] = "true"

    def clean_contact_phone(self) -> str:
        phone = self.cleaned_data["contact_phone"].strip()
        digits = re.sub(r"\D", "", phone)

        if not re.fullmatch(r"\+?[0-9\s().-]+", phone) or not 7 <= len(digits) <= 15:
            raise forms.ValidationError("Enter a valid phone number.")

        return phone

    def clean_event_date(self):
        event_date = self.cleaned_data["event_date"]

        if event_date < date.today():
            raise forms.ValidationError("Choose today or a future date.")

        return event_date

    @transaction.atomic
    def save(self, commit: bool = True) -> PartyBuild:
        """Save the build and trusted price snapshots in one transaction."""

        build = super().save(commit=False)
        selected_addons = list(self.cleaned_data.get("addons", []))
        quote = calculate_party_quote(self.package, selected_addons)

        build.package = self.package
        build.total_price = quote.total_price

        if not commit:
            return build

        build.save()
        PartyBuildAddon.objects.bulk_create(
            PartyBuildAddon(
                build=build,
                addon=addon,
                unit_price=addon.price,
            )
            for addon in selected_addons
        )

        return build
