"""Owner booking-state actions kept separate from request handling."""
# This service applies management actions to customer bookings while preserving the price and
# party-size history captured at checkout.
# It separates operational decisions from page rendering and records sensitive changes for later
# review.

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.permissions import can_access_full_management
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


# This function handles change booking status as part of this module’s workflow.
# It keeps the repeated decision in one place so callers receive the same result and controlled
# failure behaviour.
@transaction.atomic
def change_booking_status(*, booking: PartyBuild, status: str, actor, note: str = "") -> PartyBuild:
    if not can_access_full_management(actor):
        raise PermissionDenied("Only an Administrator or Owner can change booking status.")
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


# This function handles send to manual review as part of this module’s workflow.
# It keeps the repeated decision in one place so callers receive the same result and controlled
# failure behaviour.
@transaction.atomic
def send_to_manual_review(*, booking: PartyBuild, actor, reason: str) -> PartyBuild:
    """Move an active booking into the owner attention queue.

    The permission check lives in the service as well as the view so future
    command-line or API entry points cannot bypass the same business rule.
    Completed and cancelled bookings are historical records and must not be
    returned to an operational assignment state.
    """

    if not can_access_full_management(actor):
        raise PermissionDenied("Only an Administrator or Owner can send bookings to manual review.")
    locked = PartyBuild.objects.select_for_update().get(pk=booking.pk)
    if locked.status in {PartyBuild.Status.COMPLETED, PartyBuild.Status.CANCELLED}:
        raise ValidationError(
            "Completed or cancelled bookings cannot be sent to manual review."
        )
    if locked.assignment_state == PartyBuild.AssignmentState.MANUAL_REVIEW:
        raise ValidationError("This booking is already waiting for manual review.")

    cleaned_reason = reason.strip()
    if not cleaned_reason:
        raise ValidationError("Explain why the booking needs manual review.")

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
        after={"assignment_state": locked.assignment_state, "reason": cleaned_reason},
    )
    return locked
