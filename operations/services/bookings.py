"""Owner booking-state actions kept separate from request handling."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.permissions import is_owner
from party_builder.models import PartyBuild

from ..models import PartyAssignment
from .audit import record_audit


ALLOWED_STATUS_TRANSITIONS = {
    PartyBuild.Status.SUBMITTED: {PartyBuild.Status.CONTACTED, PartyBuild.Status.CANCELLED},
    PartyBuild.Status.CONTACTED: {PartyBuild.Status.CONFIRMED, PartyBuild.Status.CANCELLED},
    PartyBuild.Status.CONFIRMED: {PartyBuild.Status.COMPLETED, PartyBuild.Status.CANCELLED},
    PartyBuild.Status.COMPLETED: set(),
    PartyBuild.Status.CANCELLED: set(),
}


@transaction.atomic
def change_booking_status(*, booking: PartyBuild, status: str, actor, note: str = "") -> PartyBuild:
    if not is_owner(actor):
        raise PermissionDenied("Only an owner can change booking status.")
    locked = PartyBuild.objects.select_for_update().get(pk=booking.pk)
    if status not in ALLOWED_STATUS_TRANSITIONS.get(locked.status, set()):
        raise ValidationError("That booking status change is not allowed.")
    if status == PartyBuild.Status.COMPLETED and locked.event_date > timezone.localdate():
        raise ValidationError("A party cannot be completed before its event date.")
    before = locked.status
    locked.status = status
    update_fields = ["status", "updated_at"]
    if status == PartyBuild.Status.COMPLETED:
        locked.completed_at = timezone.now()
        update_fields.append("completed_at")
    if status == PartyBuild.Status.CANCELLED:
        locked.assignments.filter(
            status__in=(PartyAssignment.Status.PENDING, PartyAssignment.Status.ACCEPTED)
        ).update(status=PartyAssignment.Status.CANCELLED, responded_at=timezone.now())
        locked.assignment_state = PartyBuild.AssignmentState.UNASSIGNED
        update_fields.append("assignment_state")
    locked.save(update_fields=update_fields)
    record_audit(
        actor=actor,
        event_type="booking_status_changed",
        target=locked,
        summary=f"{actor} changed booking {locked.public_id} from {before} to {status}.",
        before={"status": before},
        after={
            "status": status,
            "note": note.strip(),
            "completed_at": locked.completed_at.isoformat() if locked.completed_at else None,
        },
    )
    return locked


@transaction.atomic
def send_to_manual_review(*, booking: PartyBuild, actor, reason: str) -> PartyBuild:
    locked = PartyBuild.objects.select_for_update().get(pk=booking.pk)
    previous = locked.assignment_state
    # A booking under manual review must not remain on a worker's confirmed
    # schedule. Previous offers stay in history as superseded records.
    locked.assignments.filter(
        status__in=(PartyAssignment.Status.PENDING, PartyAssignment.Status.ACCEPTED)
    ).update(
        status=PartyAssignment.Status.SUPERSEDED,
        responded_at=timezone.now(),
    )
    locked.assignment_state = PartyBuild.AssignmentState.MANUAL_REVIEW
    locked.assignment_requested_at = timezone.now()
    locked.save(update_fields=["assignment_state", "assignment_requested_at", "updated_at"])
    record_audit(
        actor=actor,
        event_type="booking_manual_review",
        target=locked,
        summary=f"{actor} sent booking {locked.public_id} to manual review.",
        before={"assignment_state": previous},
        after={"assignment_state": locked.assignment_state, "reason": reason.strip()},
    )
    return locked
