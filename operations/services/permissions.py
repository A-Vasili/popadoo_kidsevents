from __future__ import annotations

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.models import WorkerProfile
from accounts.permissions import OWNER_GROUP, PRICING_GROUP, WORKER_GROUP, is_owner

from ..models import AuditEvent


def _require_owner(actor):
    if not is_owner(actor) or not actor.has_perm("accounts.manage_worker_roles"):
        raise PermissionDenied("Owner permission is required.")


@transaction.atomic
def promote_to_worker(user, actor):
    _require_owner(actor)
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


@transaction.atomic
def demote_worker(user, actor):
    _require_owner(actor)
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


@transaction.atomic
def grant_pricing_management(user, actor):
    _require_owner(actor)
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


@transaction.atomic
def revoke_pricing_management(user, actor):
    _require_owner(actor)
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
