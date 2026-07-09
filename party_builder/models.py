from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse


class PartyPackage(models.Model):
    """A starting package containing the essential party experiences."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    short_description = models.CharField(max_length=240)
    base_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    duration_minutes = models.PositiveIntegerField(
        default=120,
        validators=[MinValueValidator(30), MaxValueValidator(600)],
    )
    included_guest_count = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(200)],
    )
    included_experiences = models.TextField(
        help_text="Enter one included experience per line."
    )
    is_default = models.BooleanField(
        default=False,
        help_text="The default package shown when the builder opens.",
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
        return reverse(
            "party_builder:party_builder_package",
            kwargs={"package_slug": self.slug},
        )


class AddonExperience(models.Model):
    """An optional paid experience that can be added to a party package."""

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
        help_text="A short decorative symbol; it is hidden from assistive technology.",
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
    """A saved customer configuration with server-side price snapshots."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        CONTACTED = "contacted", "Contacted"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    package = models.ForeignKey(
        PartyPackage,
        on_delete=models.PROTECT,
        related_name="builds",
    )
    addons = models.ManyToManyField(
        AddonExperience,
        through="PartyBuildAddon",
        related_name="party_builds",
        blank=True,
    )
    contact_name = models.CharField(max_length=120)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=30)
    event_date = models.DateField()
    guest_count = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(200)]
    )
    notes = models.TextField(blank=True, max_length=1500)
    total_price = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Server-calculated price snapshot at submission time.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.contact_name} — {self.package.name} ({self.event_date})"

    def get_absolute_url(self) -> str:
        return reverse(
            "party_builder:party_builder_success",
            kwargs={"public_id": self.public_id},
        )


class PartyBuildAddon(models.Model):
    """Join model preserving the addon price used for a submitted build."""

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
