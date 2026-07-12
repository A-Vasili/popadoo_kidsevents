"""Owner booking-state actions kept separate from request handling."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from party_builder.models import PartyBuild

from ..models import PartyAssignment
from .audit import record_audit


ALLOWED_STATUS_TRANSITIONS = {
    PartyBuild.Status.SUBMITTED: {PartyBuild.Status.CONTACTED, PartyBuild.Status.CANCELLED},
    PartyBuild.Status.CONTACTED: {PartyBuild.Status.CONFIRMED, PartyBuild.Status.CANCELLED},
    PartyBuild.Status.CONFIRMED: {PartyBuild.Status.CANCELLED},
    PartyBuild.Status.CANCELLED: set(),
}


@transaction.atomic
def change_booking_status(*, booking: PartyBuild, status: str, actor, note: str = "") -> PartyBuild:
    locked = PartyBuild.objects.select_for_update().get(pk=booking.pk)
    if status not in ALLOWED_STATUS_TRANSITIONS.get(locked.status, set()):
        raise ValidationError("That booking status change is not allowed.")
    before = locked.status
    locked.status = status
    update_fields = ["status", "updated_at"]
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
        after={"status": status, "note": note.strip()},
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
