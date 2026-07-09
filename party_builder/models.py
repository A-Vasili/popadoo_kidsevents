from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse


class PartyPackage(models.Model):
    """The essential Popadoo experience used as the checkout foundation."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    short_description = models.CharField(max_length=240)
    base_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Reference price for the smallest active guest bracket.",
    )
    duration_minutes = models.PositiveIntegerField(
        default=120,
        validators=[MinValueValidator(30), MaxValueValidator(600)],
    )
    included_guest_count = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(200)],
    )
    included_experiences = models.TextField(
        help_text="Enter one included experience per line."
    )
    is_default = models.BooleanField(
        default=False,
        help_text="The package used when the multi-step checkout opens.",
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "name")
        constraints = [
            models.CheckConstraint(
                condition=Q(base_price__gte=0),
                name="party_package_base_price_non_negative",
            ),
            models.UniqueConstraint(
                fields=("is_default",),
                condition=Q(is_default=True),
                name="party_builder_single_default_package",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def included_experiences_list(self) -> list[str]:
        """Return clean list items for semantic template rendering."""

        return [
            item.strip()
            for item in self.included_experiences.splitlines()
            if item.strip()
        ]

    def get_absolute_url(self) -> str:
        return reverse("party_builder:party_builder_package_options")


class GuestPriceTier(models.Model):
    """A fixed package price for a clearly defined children-count bracket."""

    package = models.ForeignKey(
        PartyPackage,
        on_delete=models.CASCADE,
        related_name="guest_price_tiers",
    )
    label = models.CharField(max_length=60)
    min_guests = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(200)]
    )
    max_guests = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(200)]
    )
    total_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "min_guests")
        constraints = [
            models.CheckConstraint(
                condition=Q(total_price__gte=0),
                name="guest_tier_price_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(max_guests__gte=models.F("min_guests")),
                name="guest_tier_valid_range",
            ),
            models.UniqueConstraint(
                fields=("package", "min_guests", "max_guests"),
                name="guest_tier_unique_range_per_package",
            ),
            models.UniqueConstraint(
                fields=("package",),
                condition=Q(is_default=True),
                name="guest_tier_single_default_per_package",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.package.name}: {self.label}"

    @property
    def price_per_child_at_capacity(self) -> Decimal:
        """Show the effective rate when the bracket is filled to capacity."""

        if not self.max_guests:
            return Decimal("0.00")
        return (self.total_price / Decimal(self.max_guests)).quantize(
            Decimal("0.01")
        )

    def contains_guest_count(self, guest_count: int) -> bool:
        return self.min_guests <= guest_count <= self.max_guests


class AddonExperience(models.Model):
    """An optional paid experience that can be added to the base package."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    short_description = models.CharField(max_length=260)
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    duration_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Additional event duration. Use 0 when the addon runs in parallel.",
        validators=[MaxValueValidator(600)],
    )
    icon = models.CharField(
        max_length=8,
        default="✦",
        help_text="A short decorative symbol hidden from assistive technology.",
    )
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "name")
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="party_addon_price_non_negative",
            )
        ]

    def __str__(self) -> str:
        return self.name


class PartyBuild(models.Model):
    """A completed simulated order with trusted server-side price snapshots."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        CONTACTED = "contacted", "Contacted"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        SIMULATED = "simulated", "Simulated payment accepted"
        NOT_REQUIRED = "not_required", "No payment data"

    class AssignmentState(models.TextChoices):
        UNASSIGNED = "unassigned", "Unassigned"
        PENDING = "pending_acceptance", "Awaiting worker response"
        ASSIGNED = "assigned", "Worker assigned"
        MANUAL_REVIEW = "manual_review", "Owner review required"

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="party_bookings",
        help_text="Empty for guest checkouts.",
    )
    package = models.ForeignKey(
        PartyPackage,
        on_delete=models.PROTECT,
        related_name="builds",
    )
    guest_tier = models.ForeignKey(
        GuestPriceTier,
        on_delete=models.PROTECT,
        related_name="builds",
        null=True,
        blank=True,
        help_text="Nullable only for legacy requests created before tiered pricing.",
    )
    addons = models.ManyToManyField(
        AddonExperience,
        through="PartyBuildAddon",
        related_name="party_builds",
        blank=True,
    )

    # Personal and event details collected during checkout step two.
    contact_name = models.CharField(max_length=120)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=30)
    event_date = models.DateField()
    event_time = models.TimeField(null=True, blank=True)
    event_address = models.CharField(max_length=240, blank=True)
    postal_code = models.CharField(
        max_length=10,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9][A-Za-z0-9\s-]{2,9}$",
                message="Enter a valid postal code.",
            )
        ],
    )
    guest_count = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(200)]
    )
    notes = models.TextField(blank=True, max_length=1500)

    # Snapshots protect historical orders when administrators change prices later.
    guest_tier_label = models.CharField(max_length=60, blank=True)
    package_price = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    addon_price = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_price = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Server-calculated total at simulated checkout.",
    )

    # Only non-sensitive payment metadata is stored. Card number and CVV are discarded.
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.NOT_REQUIRED,
    )
    card_brand = models.CharField(max_length=30, blank=True)
    card_last_four = models.CharField(max_length=4, blank=True)
    payment_reference = models.CharField(max_length=40, blank=True)
    checkout_completed_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    assignment_state = models.CharField(
        max_length=30,
        choices=AssignmentState.choices,
        default=AssignmentState.UNASSIGNED,
    )
    assignment_requested_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.contact_name} — {self.package.name} ({self.event_date})"

    def get_absolute_url(self) -> str:
        return reverse(
            "party_builder:party_builder_order_success",
            kwargs={"public_id": self.public_id},
        )


class PartyBuildAddon(models.Model):
    """Join model preserving the addon price used for a completed checkout."""

    build = models.ForeignKey(
        PartyBuild,
        on_delete=models.CASCADE,
        related_name="addon_items",
    )
    addon = models.ForeignKey(
        AddonExperience,
        on_delete=models.PROTECT,
        related_name="build_items",
    )
    unit_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ("addon__display_order", "addon__name")
        constraints = [
            models.UniqueConstraint(
                fields=("build", "addon"),
                name="party_build_unique_addon",
            )
        ]

    def __str__(self) -> str:
        return f"{self.build.public_id}: {self.addon.name}"
