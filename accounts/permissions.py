"""Business-role checks shared by views, services, and navigation.

Django superusers are Popadoo Administrators. Owners are ordinary accounts in
Popadoo's Owners group. Keeping those roles separate prevents an Owner from
quietly gaining system-level privileges while still allowing both roles to run
the business through the custom management panel.
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


def is_administrator(user: AbstractBaseUser) -> bool:
    """Identify system administrators without treating them as Owners."""

    return bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_superuser", False)
    )


def is_owner(user: AbstractBaseUser) -> bool:
    """Identify business Owners, which are deliberately not superusers."""

    return bool(
        getattr(user, "is_authenticated", False)
        and not getattr(user, "is_superuser", False)
        and user_in_group(user, OWNER_GROUP)
    )


def can_access_full_management(user: AbstractBaseUser) -> bool:
    """Allow Administrators and Owners into the complete business panel."""

    return bool(is_administrator(user) or is_owner(user))


def can_create_owner(user: AbstractBaseUser) -> bool:
    """Only an Administrator may create another protected Owner account."""

    return is_administrator(user)


def is_worker(user: AbstractBaseUser) -> bool:
    """Return true only for an active worker, never for an Administrator."""

    if not getattr(user, "is_authenticated", False):
        return False
    if not user_in_group(user, WORKER_GROUP):
        return False
    profile = getattr(user, "worker_profile", None)
    return bool(profile and profile.is_active_worker)


def can_manage_pricing(user: AbstractBaseUser) -> bool:
    """Allow full managers and explicitly delegated worker pricing managers."""

    return bool(
        can_access_full_management(user)
        or (
            user_in_group(user, PRICING_GROUP)
            and user.has_perm("party_builder.change_partypackage")
            and user.has_perm("party_builder.change_addonexperience")
        )
    )


def can_access_operations(user: AbstractBaseUser) -> bool:
    """Allow full managers to redirect safely and workers to use the staff portal."""

    return bool(can_access_full_management(user) or is_worker(user))


def can_manage_workers(user: AbstractBaseUser) -> bool:
    """Require full management access and the worker-role permission."""

    return bool(
        can_access_full_management(user)
        and user.has_perm("accounts.manage_worker_roles")
    )


def role_context(request):
    """Expose navigation flags using one group lookup for the current request.

    These flags decide which links are shown. Private views and services still
    repeat the permission checks because hiding a link is not security.
    """

    user = request.user
    empty = {
        "nav_is_administrator": False,
        "nav_is_owner": False,
        "nav_is_worker": False,
        "nav_can_access_operations": False,
        "nav_can_manage_pricing": False,
        "nav_can_access_management": False,
        "nav_can_access_full_management": False,
        "nav_can_create_owner": False,
    }
    if not getattr(user, "is_authenticated", False):
        return empty

    group_names = set(user.groups.values_list("name", flat=True))
    administrator = bool(user.is_superuser)
    owner = bool(not administrator and OWNER_GROUP in group_names)
    profile = getattr(user, "worker_profile", None) if WORKER_GROUP in group_names else None
    worker = bool(WORKER_GROUP in group_names and profile and profile.is_active_worker)
    full_management = administrator or owner
    pricing = bool(
        full_management
        or (
            PRICING_GROUP in group_names
            and user.has_perm("party_builder.change_partypackage")
            and user.has_perm("party_builder.change_addonexperience")
        )
    )
    return {
        "nav_is_administrator": administrator,
        "nav_is_owner": owner,
        "nav_is_worker": worker,
        "nav_can_access_operations": full_management or worker,
        "nav_can_manage_pricing": pricing,
        "nav_can_access_management": full_management or pricing,
        "nav_can_access_full_management": full_management,
        "nav_can_create_owner": administrator,
    }
