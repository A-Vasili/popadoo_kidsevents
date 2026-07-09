# This file defines the forms used by workers and owners in the operations area.
# Comments in this file explain the purpose of each section without changing how the program works.

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from accounts.models import WorkerProfile
from party_builder.models import AddonExperience, GuestPriceTier, PartyPackage

from .models import WorkerAvailability


# This variable stores the active Django user model so the project remains compatible with Django settings.
User = get_user_model()


# This helper adds labels and error links that make the form easier to understand with assistive technology.
def apply_accessibility(form: forms.BaseForm) -> None:
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


class WorkerProfileForm(forms.ModelForm):
    """Allow workers to maintain their own operational contact details."""

    class Meta:
        model = WorkerProfile
        fields = ("display_name", "phone")

    # This method prepares the object and adjusts its starting values.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_accessibility(self)


class WorkerAvailabilityForm(forms.ModelForm):
    """Create or edit one future worker availability window."""

    class Meta:
        model = WorkerAvailability
        fields = ("start_at", "end_at", "availability_type", "notes")
        widgets = {
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "notes": forms.TextInput(attrs={"placeholder": "Optional note"}),
        }

    # This method prepares the object and adjusts its starting values.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_accessibility(self)


# This form gathers and checks the information needed for decline assignment.
class DeclineAssignmentForm(forms.Form):
    reason = forms.CharField(
        max_length=500,
        label="Reason for declining",
        help_text="This helps the owner understand availability and contact another worker.",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
    )

    # This method prepares the object and adjusts its starting values.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_accessibility(self)


# This form gathers and checks the information needed for manual assignment.
class ManualAssignmentForm(forms.Form):
    worker = forms.ModelChoiceField(queryset=WorkerProfile.objects.none())
    already_agreed = forms.BooleanField(
        required=False,
        label="The worker has already agreed; add directly to the confirmed schedule",
    )
    override_reason = forms.CharField(
        required=False,
        max_length=500,
        label="Conflict override reason",
        help_text="Required only when the chosen worker has a scheduling conflict.",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    # This method prepares the object and adjusts its starting values.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["worker"].queryset = WorkerProfile.objects.filter(
            is_active_worker=True,
            user__is_active=True,
            user__groups__name="Workers",
        ).select_related("user").distinct()
        apply_accessibility(self)


# This form gathers and checks the information needed for package pricing.
class PackagePricingForm(forms.ModelForm):
    # This inner Meta class tells Django which database model and fields this form or admin section uses.
    class Meta:
        model = PartyPackage
        fields = ("base_price", "duration_minutes", "is_active")

    # This method prepares the object and adjusts its starting values.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_accessibility(self)


# This form gathers and checks the information needed for guest tier pricing.
class GuestTierPricingForm(forms.ModelForm):
    # This inner Meta class tells Django which database model and fields this form or admin section uses.
    class Meta:
        model = GuestPriceTier
        fields = ("label", "min_guests", "max_guests", "total_price", "is_active")

    # This method prepares the object and adjusts its starting values.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_accessibility(self)


# This form gathers and checks the information needed for addon pricing.
class AddonPricingForm(forms.ModelForm):
    # This inner Meta class tells Django which database model and fields this form or admin section uses.
    class Meta:
        model = AddonExperience
        fields = (
            "name",
            "slug",
            "short_description",
            "price",
            "duration_minutes",
            "icon",
            "is_featured",
            "is_active",
            "display_order",
        )

    # This method prepares the object and adjusts its starting values.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_accessibility(self)
