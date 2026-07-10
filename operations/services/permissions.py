# This file safely promotes, demotes, and grants pricing rights to users.
# Comments in this file explain the purpose of each section without changing how the program works.

from __future__ import annotations

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.models import WorkerProfile
from accounts.permissions import OWNER_GROUP, PRICING_GROUP, WORKER_GROUP, is_owner

from ..models import AuditEvent


# This helper stops the action unless the signed-in user has owner-level access.
def _require_owner(actor):
    if not is_owner(actor) or not actor.has_perm("accounts.manage_worker_roles"):
        raise PermissionDenied("Owner permission is required.")


def _reject_protected_account(user):
    """Keep superusers and owners outside the worker-management workflow.

    Owner accounts are maintained through their own profile and, when needed,
    by a Django administrator. This prevents one owner from changing another
    owner's role through a crafted request.
    """

    if user.is_superuser or user.groups.filter(name=OWNER_GROUP).exists():
        raise PermissionDenied(
            "Owner and administrator accounts cannot be changed here."
        )


# This helper changes a user role through the approved permission workflow.
@transaction.atomic
def promote_to_worker(user, actor):
    _require_owner(actor)
    _reject_protected_account(user)
    Workers, _ = Group.objects.get_or_create(name=WORKER_GROUP)
    Workers.user_set.add(user)
    profile, _ = WorkerProfile.objects.get_or_create(user=user)
    profile.is_active_worker = True
    profile.save(update_fields=["is_active_worker", "updated_at"])
    AuditEvent.objects.create(
        actor=actor,
        event_type="worker_promoted",
        object_type="User",
        object_id=str(user.pk),
        summary=f"{actor} promoted {user} to worker.",
    )
    return profile


# This helper changes a user role through the approved permission workflow.
@transaction.atomic
def demote_worker(user, actor):
    _require_owner(actor)
    _reject_protected_account(user)
    worker_group = Group.objects.filter(name=WORKER_GROUP).first()
    if worker_group:
        worker_group.user_set.remove(user)
    pricing_group = Group.objects.filter(name=PRICING_GROUP).first()
    if pricing_group:
        pricing_group.user_set.remove(user)
    profile = getattr(user, "worker_profile", None)
    if profile:
        profile.is_active_worker = False
        profile.save(update_fields=["is_active_worker", "updated_at"])
    AuditEvent.objects.create(
        actor=actor,
        event_type="worker_demoted",
        object_type="User",
        object_id=str(user.pk),
        summary=f"{actor} demoted {user} to customer.",
    )


# This helper changes a delegated permission and records the action.
@transaction.atomic
def grant_pricing_management(user, actor):
    _require_owner(actor)
    _reject_protected_account(user)
    if not user.groups.filter(name=WORKER_GROUP).exists():
        raise ValidationError("Pricing rights can be granted only to a worker.")
    group, _ = Group.objects.get_or_create(name=PRICING_GROUP)
    group.user_set.add(user)
    AuditEvent.objects.create(
        actor=actor,
        event_type="pricing_rights_granted",
        object_type="User",
        object_id=str(user.pk),
        summary=f"{actor} granted pricing rights to {user}.",
    )


# This helper changes a delegated permission and records the action.
@transaction.atomic
def revoke_pricing_management(user, actor):
    _require_owner(actor)
    _reject_protected_account(user)
    group = Group.objects.filter(name=PRICING_GROUP).first()
    if group:
        group.user_set.remove(user)
    AuditEvent.objects.create(
        actor=actor,
        event_type="pricing_rights_revoked",
        object_type="User",
        object_id=str(user.pk),
        summary=f"{actor} revoked pricing rights from {user}.",
    )
