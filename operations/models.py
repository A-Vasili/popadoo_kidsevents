
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from accounts.models import WorkerProfile
from party_builder.models import PartyBuild


class WorkerAvailability(models.Model):
    """A worker-defined time window showing availability or a blocked period."""

    class AvailabilityType(models.TextChoices):
        AVAILABLE = "available", "Available"
        PREFERRED = "preferred", "Preferred"
        UNAVAILABLE = "unavailable", "Unavailable"

    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="availability_periods",
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    availability_type = models.CharField(
        max_length=20,
        choices=AvailabilityType.choices,
        default=AvailabilityType.AVAILABLE,
    )
    notes = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("start_at", "worker__display_name")
        permissions = [
            ("manage_all_availability", "Can manage every worker's availability"),
        ]
        indexes = [
            models.Index(fields=("worker", "start_at", "end_at")),
        ]

    # This validation step checks values that depend on more than one form field.
    def clean(self) -> None:
        super().clean()
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError({"end_at": "End time must be after start time."})

    def __str__(self) -> str:
        return f"{self.worker}: {self.get_availability_type_display()} {self.start_at:%d/%m/%Y %H:%M}"


class PartyAssignment(models.Model):
    """Preserve each automatic or manual worker-assignment attempt."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending response"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        SUPERSEDED = "superseded", "Superseded"
        CANCELLED = "cancelled", "Cancelled"

    # This database model stores source information.
    class Source(models.TextChoices):
        AUTOMATIC = "automatic", "Automatic"
        OWNER_MANUAL = "owner_manual", "Owner manual"
        ADMIN_OVERRIDE = "admin_override", "Administrator override"

    party_build = models.ForeignKey(
        PartyBuild,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    assignment_source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.AUTOMATIC,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_party_assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    decline_reason = models.CharField(max_length=500, blank=True)
    owner_note = models.CharField(max_length=500, blank=True)
    conflict_override_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-assigned_at",)
        permissions = [
            ("view_all_schedules", "Can view all worker schedules"),
            ("manually_assign_party", "Can manually assign parties to workers"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("party_build",),
                condition=Q(status="accepted"),
                name="operations_one_accepted_assignment_per_booking",
            ),
            models.UniqueConstraint(
                fields=("party_build", "worker"),
                condition=Q(status="pending"),
                name="operations_one_pending_offer_per_worker_booking",
            ),
        ]
        indexes = [
            models.Index(fields=("worker", "status", "assigned_at")),
            models.Index(fields=("party_build", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.party_build.public_id} → {self.worker} ({self.status})"


class AuditEvent(models.Model):
    """Human-readable audit history for sensitive owner and worker actions."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="popadoo_audit_events",
    )
    event_type = models.CharField(max_length=80)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80, blank=True)
    summary = models.CharField(max_length=300)
    before_data = models.JSONField(default=dict, blank=True)
    after_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("event_type", "created_at")),
            models.Index(fields=("actor", "created_at")),
            models.Index(fields=("object_type", "object_id")),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}: {self.summary}"
