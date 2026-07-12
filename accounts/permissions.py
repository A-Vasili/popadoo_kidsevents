"""Role checks used by views, services, and navigation.

This module identifies Popadoo business roles. Navigation flags are convenient
for presentation only; private views still enforce permissions server-side.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

OWNER_GROUP = "Owners"
WORKER_GROUP = "Workers"
PRICING_GROUP = "Pricing Managers"


def user_in_group(user: AbstractBaseUser, group_name: str) -> bool:
    """Return group membership without assuming the user is authenticated."""

    return bool(
        getattr(user, "is_authenticated", False)
        and user.groups.filter(name=group_name).exists()
    )


def is_owner(user: AbstractBaseUser) -> bool:
    return bool(getattr(user, "is_superuser", False) or user_in_group(user, OWNER_GROUP))


def is_worker(user: AbstractBaseUser) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not user_in_group(user, WORKER_GROUP):
        return False
    profile = getattr(user, "worker_profile", None)
    return bool(profile and profile.is_active_worker)


def can_manage_pricing(user: AbstractBaseUser) -> bool:
    """Allow owners and explicitly delegated worker pricing managers."""

    return bool(
        is_owner(user)
        or (
            user_in_group(user, PRICING_GROUP)
            and user.has_perm("party_builder.change_partypackage")
            and user.has_perm("party_builder.change_addonexperience")
        )
    )


def can_access_operations(user: AbstractBaseUser) -> bool:
    return bool(is_owner(user) or is_worker(user))


def can_manage_workers(user: AbstractBaseUser) -> bool:
    return bool(is_owner(user) and user.has_perm("accounts.manage_worker_roles"))


def role_context(request):
    """Expose stable role flags used by shared navigation templates."""

    user = request.user
    owner = is_owner(user)
    pricing = can_manage_pricing(user)
    return {
        "nav_is_owner": owner,
        "nav_is_worker": is_worker(user),
        "nav_can_access_operations": can_access_operations(user),
        "nav_can_manage_pricing": pricing,
        "nav_can_access_management": owner or pricing,
    }
