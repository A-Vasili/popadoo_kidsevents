
from __future__ import annotations

import secrets
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, router
from django.db.models import Q
from django.urls import reverse

from .validators import (
    addon_image_upload_to,
    category_image_upload_to,
    package_image_upload_to,
    validate_catalogue_image,
)


def _validate_constraints_except(instance, excluded_names: set[str], exclude=None) -> None:
    """Validate model constraints except defaults switched by a transaction.

    Conditional unique constraints correctly protect the database, but Django's
    ModelForm validation runs before the service can clear the old default row.
    Skipping only those two checks here allows an atomic default switch while
    every other model and database constraint remains active.
    """

    errors = {}
    using = router.db_for_write(instance.__class__, instance=instance)
    for model_class, model_constraints in instance.get_constraints():
        for constraint in model_constraints:
            if constraint.name in excluded_names:
                continue
            try:
                constraint.validate(
                    model_class,
                    instance,
                    exclude=exclude,
                    using=using,
                )
            except ValidationError as error:
                if (
                    getattr(error, "code", None) == "unique"
                    and len(constraint.fields) == 1
                ):
                    errors.setdefault(constraint.fields[0], []).append(error)
                else:
                    errors = error.update_error_dict(errors)
    if errors:
        raise ValidationError(errors)


class Category(models.Model):
    """A catalogue category; assigning a parent creates a subcategory."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True, max_length=1000)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    image = models.ImageField(
        upload_to=category_image_upload_to,
        validators=[validate_catalogue_image],
        blank=True,
    )
    image_alt_text = models.CharField(
        max_length=180,
        blank=True,
        help_text="Describe the image for visitors who cannot see it.",
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("display_order", "name")
        verbose_name_plural = "categories"
        indexes = [
            models.Index(fields=("is_active", "display_order", "name")),
            models.Index(fields=("parent", "is_active")),
        ]

    def __str__(self) -> str:
        return self.name if self.parent_id is None else f"{self.parent.name} / {self.name}"

    def clean(self) -> None:
        """Reject self-parenting and parent choices underneath this category."""

        super().clean()
        self.name = (self.name or "").strip()
        self.description = (self.description or "").strip()
        self.image_alt_text = (self.image_alt_text or "").strip()
        if not self.name:
            raise ValidationError({"name": "Enter a category name."})
        if self.pk and self.parent_id == self.pk:
            raise ValidationError({"parent": "A category cannot be its own parent."})

        parent = self.parent
        visited = set()
        while parent is not None:
            if parent.pk in visited:
                raise ValidationError({"parent": "The selected category hierarchy is circular."})
            visited.add(parent.pk)
            if self.pk and parent.pk == self.pk:
                raise ValidationError(
                    {"parent": "A category cannot be placed underneath one of its subcategories."}
                )
            parent = parent.parent

        if self.image and not self.image_alt_text:
            raise ValidationError({"image_alt_text": "Add meaningful alternative text for this image."})


class PartyPackage(models.Model):
    """The essential Popadoo experience used as the checkout foundation."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="packages",
    )
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
    image = models.ImageField(
        upload_to=package_image_upload_to,
        validators=[validate_catalogue_image],
        blank=True,
    )
    image_alt_text = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ("display_order", "name")
        indexes = [models.Index(fields=("is_active", "display_order", "name"))]
        constraints = [
            models.CheckConstraint(
                condition=Q(base_price__gte=0),
                name="party_package_base_price_non_negative",
            ),
            # The database also enforces the single-default rule so imports,
            # scripts, and future code cannot accidentally create two defaults.
            models.UniqueConstraint(
                fields=("is_default",),
                condition=Q(is_default=True),
                name="party_builder_single_default_package",
            ),
        ]

    def clean(self) -> None:
        """Keep text tidy and ensure default records remain selectable."""

        super().clean()
        self.name = (self.name or "").strip()
        self.short_description = (self.short_description or "").strip()
        self.included_experiences = (self.included_experiences or "").strip()
        self.image_alt_text = (self.image_alt_text or "").strip()
        if self.is_default and not self.is_active:
            raise ValidationError({"is_active": "The default package must remain active."})
        if self.image and not self.image_alt_text:
            raise ValidationError({"image_alt_text": "Add meaningful alternative text for this image."})

    def validate_constraints(self, exclude=None) -> None:
        _validate_constraints_except(
            self,
            {"party_builder_single_default_package"},
            exclude=exclude,
        )

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

    def clean(self) -> None:
        """Validate active ranges before they reach checkout pricing."""

        super().clean()
        self.label = (self.label or "").strip()
        if self.min_guests and self.max_guests and self.max_guests < self.min_guests:
            raise ValidationError({"max_guests": "Maximum guests must be at least the minimum."})
        if self.is_default and not self.is_active:
            raise ValidationError({"is_active": "The default price tier must remain active."})
        if self.package_id and self.is_active and self.min_guests and self.max_guests:
            overlapping = GuestPriceTier.objects.filter(
                package_id=self.package_id,
                is_active=True,
                min_guests__lte=self.max_guests,
                max_guests__gte=self.min_guests,
            )
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError(
                    "This active guest range overlaps another active tier for the package."
                )

    def validate_constraints(self, exclude=None) -> None:
        _validate_constraints_except(
            self,
            {"guest_tier_single_default_per_package"},
            exclude=exclude,
        )

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
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="addons",
    )
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
    image = models.ImageField(
        upload_to=addon_image_upload_to,
        validators=[validate_catalogue_image],
        blank=True,
    )
    image_alt_text = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ("display_order", "name")
        indexes = [models.Index(fields=("is_active", "is_featured", "display_order"))]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="party_addon_price_non_negative",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.name = (self.name or "").strip()
        self.short_description = (self.short_description or "").strip()
        self.image_alt_text = (self.image_alt_text or "").strip()
        if self.image and not self.image_alt_text:
            raise ValidationError({"image_alt_text": "Add meaningful alternative text for this image."})

    def __str__(self) -> str:
        return self.name


REVIEW_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def format_review_code(raw: str) -> str:
    """Return a normalized human-readable code without ambiguous characters."""

    compact = "".join(character for character in (raw or "").upper() if character.isalnum())
    if compact.startswith("POP"):
        compact = compact[3:]
    if len(compact) != 8 or any(character not in REVIEW_CODE_ALPHABET for character in compact):
        return ""
    return f"POP-{compact[:4]}-{compact[4:]}"


def generate_review_code_candidate() -> str:
    """Create one readable candidate; database uniqueness is checked separately."""

    body = "".join(secrets.choice(REVIEW_CODE_ALPHABET) for _ in range(8))
    return f"POP-{body[:4]}-{body[4:]}"


def generate_unique_review_code() -> str:
    """Return a code not currently stored in the booking table."""

    for _attempt in range(32):
        candidate = generate_review_code_candidate()
        # This lookup keeps normal model creation safe. The unique database
        # constraint remains the final protection if two requests race.
        if not PartyBuild.objects.filter(review_code=candidate).exists():
            return candidate
    raise RuntimeError("Unable to allocate a unique party review code.")


class PartyBuild(models.Model):
    """A completed simulated order with trusted server-side price snapshots."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        CONTACTED = "contacted", "Contacted"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    # This database model stores payment status information.
    class PaymentStatus(models.TextChoices):
        SIMULATED = "simulated", "Simulated payment accepted"
        NOT_REQUIRED = "not_required", "No payment data"

    # This database model stores assignment state information.
    class AssignmentState(models.TextChoices):
        UNASSIGNED = "unassigned", "Unassigned"
        PENDING = "pending_acceptance", "Awaiting worker response"
        ASSIGNED = "assigned", "Worker assigned"
        MANUAL_REVIEW = "manual_review", "Owner review required"

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    review_code = models.CharField(
        max_length=13,
        unique=True,
        editable=False,
        default=generate_unique_review_code,
    )
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
    completed_at = models.DateTimeField(null=True, blank=True)

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
        indexes = [
            models.Index(fields=("event_date", "status")),
            models.Index(fields=("assignment_state", "event_date")),
            models.Index(fields=("contact_email",)),
            models.Index(fields=("status", "completed_at")),
        ]

    def save(self, *args, **kwargs):
        if self.review_code:
            normalized = format_review_code(self.review_code)
            if not normalized:
                raise ValidationError({"review_code": "The party review code format is invalid."})
            self.review_code = normalized
        super().save(*args, **kwargs)

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


class PartyReview(models.Model):
    """Verified feedback for one completed customer booking.

    The review remains the single source of truth for both private company
    feedback and public testimonials. Publication is opt-in and can be
    withdrawn by the booking customer at any time.
    """

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private feedback"
        TESTIMONIAL = "testimonial", "Public testimonial"

    class TestimonialNameDisplay(models.TextChoices):
        ANONYMOUS = "anonymous", "Anonymous"
        FIRST_NAME = "first_name", "First name only"

    booking = models.OneToOneField(
        PartyBuild,
        on_delete=models.CASCADE,
        related_name="review",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="party_reviews",
    )
    package_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True, max_length=1500)
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
        db_index=True,
    )
    testimonial_name_display = models.CharField(
        max_length=20,
        choices=TestimonialNameDisplay.choices,
        default=TestimonialNameDisplay.ANONYMOUS,
    )
    testimonial_consent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(package_score__gte=1, package_score__lte=5),
                name="party_review_package_score_1_to_5",
            ),
            models.CheckConstraint(
                condition=Q(visibility__in=("private", "testimonial")),
                name="party_review_supported_visibility",
            ),
            models.CheckConstraint(
                condition=Q(testimonial_name_display__in=("anonymous", "first_name")),
                name="party_review_supported_name_display",
            ),
            # Private comments are never allowed to retain publication consent
            # or a public-facing name choice.
            models.CheckConstraint(
                condition=(
                    Q(visibility="testimonial")
                    | Q(
                        testimonial_name_display="anonymous",
                        testimonial_consent_at__isnull=True,
                    )
                ),
                name="party_review_private_state_is_not_public",
            ),
        ]
        indexes = [
            models.Index(fields=("reviewer", "updated_at")),
            models.Index(fields=("package_score", "updated_at")),
            models.Index(fields=("visibility", "updated_at")),
        ]

    def clean(self) -> None:
        super().clean()
        self.comment = (self.comment or "").strip()
        if self.visibility == self.Visibility.TESTIMONIAL and not self.comment:
            raise ValidationError(
                {"comment": "Write a comment before publishing a public testimonial."}
            )
        if self.visibility == self.Visibility.PRIVATE:
            self.testimonial_name_display = self.TestimonialNameDisplay.ANONYMOUS
            self.testimonial_consent_at = None
        if self.booking_id and self.reviewer_id:
            if self.booking.customer_id != self.reviewer_id:
                raise ValidationError("Only the customer who booked this party can review it.")
            if self.booking.status != PartyBuild.Status.COMPLETED:
                raise ValidationError("Only completed parties can be reviewed.")

    @property
    def is_public_testimonial(self) -> bool:
        """Return whether this review currently has active publication consent."""

        return (
            self.visibility == self.Visibility.TESTIMONIAL
            and self.testimonial_consent_at is not None
            and bool(self.comment.strip())
            and self.booking.status == PartyBuild.Status.COMPLETED
        )

    @property
    def public_display_name(self) -> str:
        """Return the only customer identity allowed on the public page."""

        if self.testimonial_name_display == self.TestimonialNameDisplay.FIRST_NAME:
            first_name = (self.reviewer.first_name or "").strip()
            if first_name:
                return first_name
        return "Verified customer"

    def __str__(self) -> str:
        return f"Review for {self.booking.public_id} by {self.reviewer}"


class AddonRating(models.Model):
    """A verified score for an add-on that appears in the reviewed booking."""

    review = models.ForeignKey(
        PartyReview,
        on_delete=models.CASCADE,
        related_name="addon_ratings",
    )
    build_addon = models.ForeignKey(
        PartyBuildAddon,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("build_addon__addon__display_order", "build_addon__addon__name")
        constraints = [
            models.CheckConstraint(
                condition=Q(score__gte=1, score__lte=5),
                name="addon_rating_score_1_to_5",
            ),
            models.UniqueConstraint(
                fields=("review", "build_addon"),
                name="one_rating_per_selected_booking_addon",
            ),
        ]
        indexes = [
            models.Index(fields=("build_addon", "score")),
            models.Index(fields=("review", "updated_at")),
        ]

    def clean(self) -> None:
        super().clean()
        self.comment = (self.comment or "").strip()
        if self.review_id and self.build_addon_id:
            if self.review.booking_id != self.build_addon.build_id:
                raise ValidationError(
                    "The add-on rating must belong to the same booking as the review."
                )

    def __str__(self) -> str:
        return f"{self.build_addon.addon.name}: {self.score}/5"
