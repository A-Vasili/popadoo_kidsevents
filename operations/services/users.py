"""Protected account and role changes for the custom management panel.

Only account mutations belong here. Scheduling, catalogue, and assignment rules
remain in their own services so permission changes stay easy to audit and test.
"""

from __future__ import annotations

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.models import WorkerProfile
from accounts.permissions import OWNER_GROUP, PRICING_GROUP, WORKER_GROUP, is_owner

from .audit import record_audit


def _require_owner(actor) -> None:
    if not is_owner(actor) or not actor.has_perm("accounts.manage_worker_roles"):
        raise PermissionDenied("Owner permission is required.")


def _is_owner_account(user) -> bool:
    return user.groups.filter(name=OWNER_GROUP).exists()


def _reject_role_target(user) -> None:
    """Keep administrators and owners outside worker-role mutation workflows."""

    if user.is_superuser or _is_owner_account(user):
        raise PermissionDenied("Owner and administrator accounts cannot be changed here.")


def ensure_owner_can_manage(actor, target) -> None:
    """Allow safe profile management while protecting superusers and other owners."""

    _require_owner(actor)
    if target.is_superuser:
        raise PermissionDenied("Administrator accounts are protected.")
    if _is_owner_account(target) and target.pk != actor.pk:
        raise PermissionDenied("Owners cannot modify another owner account.")


@transaction.atomic
def promote_to_worker(user, actor):
    """Promote a customer to worker and preserve any historical profile data."""

    _require_owner(actor)
    _reject_role_target(user)
    if user.groups.filter(name=WORKER_GROUP).exists():
        raise ValidationError("This account is already a worker.")

    worker_group, _ = Group.objects.get_or_create(name=WORKER_GROUP)
    worker_group.user_set.add(user)
    profile, _ = WorkerProfile.objects.get_or_create(user=user)
    before = {"worker": False, "is_active_worker": profile.is_active_worker}
    profile.is_active_worker = True
    profile.save(update_fields=["is_active_worker", "updated_at"])
    record_audit(
        actor=actor,
        event_type="worker_promoted",
        target=user,
        summary=f"{actor} promoted {user} to worker.",
        before=before,
        after={"worker": True, "is_active_worker": True},
    )
    return profile


@transaction.atomic
def demote_worker(user, actor):
    """Remove worker and pricing access without deleting historical staff records."""

    _require_owner(actor)
    _reject_role_target(user)
    if not user.groups.filter(name=WORKER_GROUP).exists():
        raise ValidationError("This account is not currently a worker.")

    had_pricing = user.groups.filter(name=PRICING_GROUP).exists()
    worker_group = Group.objects.filter(name=WORKER_GROUP).first()
    pricing_group = Group.objects.filter(name=PRICING_GROUP).first()
    if worker_group:
        worker_group.user_set.remove(user)
    if pricing_group:
        pricing_group.user_set.remove(user)

    profile = getattr(user, "worker_profile", None)
    if profile:
        profile.is_active_worker = False
        profile.save(update_fields=["is_active_worker", "updated_at"])

    record_audit(
        actor=actor,
        event_type="worker_demoted",
        target=user,
        summary=f"{actor} demoted {user} to customer.",
        before={"worker": True, "pricing": had_pricing},
        after={"worker": False, "pricing": False},
    )


@transaction.atomic
def grant_pricing_management(user, actor):
    """Grant catalogue access only to an existing worker."""

    _require_owner(actor)
    _reject_role_target(user)
    if not user.groups.filter(name=WORKER_GROUP).exists():
        raise ValidationError("Pricing rights can be granted only to a worker.")
    if user.groups.filter(name=PRICING_GROUP).exists():
        raise ValidationError("This worker already has pricing access.")

    group, _ = Group.objects.get_or_create(name=PRICING_GROUP)
    group.user_set.add(user)
    record_audit(
        actor=actor,
        event_type="pricing_rights_granted",
        target=user,
        summary=f"{actor} granted pricing rights to {user}.",
        before={"pricing": False},
        after={"pricing": True},
    )


@transaction.atomic
def revoke_pricing_management(user, actor):
    """Remove delegated catalogue access while preserving worker access."""

    _require_owner(actor)
    _reject_role_target(user)
    if not user.groups.filter(name=PRICING_GROUP).exists():
        raise ValidationError("This worker does not currently have pricing access.")

    group = Group.objects.filter(name=PRICING_GROUP).first()
    if group:
        group.user_set.remove(user)
    record_audit(
        actor=actor,
        event_type="pricing_rights_revoked",
        target=user,
        summary=f"{actor} revoked pricing rights from {user}.",
        before={"pricing": True},
        after={"pricing": False},
    )


@transaction.atomic
def set_account_active(*, target, active: bool, actor):
    """Activate or deactivate an eligible account and audit the state change."""

    ensure_owner_can_manage(actor, target)
    if target.pk == actor.pk and not active:
        raise ValidationError("You cannot deactivate the account you are currently using.")
    if target.is_active == active:
        raise ValidationError(
            "This account is already active." if active else "This account is already inactive."
        )

    before = target.is_active
    target.is_active = active
    target.save(update_fields=["is_active"])
    record_audit(
        actor=actor,
        event_type="user_activated" if active else "user_deactivated",
        target=target,
        summary=f"{actor} {'activated' if active else 'deactivated'} {target}.",
        before={"is_active": before},
        after={"is_active": active},
    )
    return target
