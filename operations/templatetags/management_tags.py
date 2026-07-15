"""Small presentation helpers for the custom management templates."""

from django import template

from accounts.permissions import (
    OWNER_GROUP,
    PRICING_GROUP,
    WORKER_GROUP,
    is_administrator,
)

register = template.Library()


def _group_names(user) -> set[str]:
    """Reuse prefetched groups on management lists instead of querying per row."""

    prefetched = getattr(user, "_prefetched_objects_cache", {}).get("groups")
    if prefetched is not None:
        return {group.name for group in prefetched}
    if not getattr(user, "is_authenticated", False):
        return set()
    return set(user.groups.values_list("name", flat=True))


@register.filter
def in_group(user, group_name: str) -> bool:
    return group_name in _group_names(user)


@register.filter
def is_administrator_account(user) -> bool:
    return is_administrator(user)


@register.filter
def is_owner_account(user) -> bool:
    return bool(not getattr(user, "is_superuser", False) and OWNER_GROUP in _group_names(user))


@register.filter
def is_worker_account(user) -> bool:
    return WORKER_GROUP in _group_names(user)


@register.filter
def is_customer_account(user) -> bool:
    group_names = _group_names(user)
    return bool(
        not getattr(user, "is_superuser", False)
        and OWNER_GROUP not in group_names
        and WORKER_GROUP not in group_names
    )


@register.filter
def management_role(user) -> str:
    if getattr(user, "is_superuser", False):
        return "Administrator"
    group_names = _group_names(user)
    if OWNER_GROUP in group_names:
        return "Owner"
    if WORKER_GROUP in group_names:
        return "Worker"
    return "Customer"


@register.filter
def has_pricing_access(user) -> bool:
    return PRICING_GROUP in _group_names(user)


@register.filter
def status_css(value: str) -> str:
    mapping = {
        "active": "success",
        "accepted": "success",
        "assigned": "success",
        "confirmed": "success",
        "completed": "success",
        "inactive": "muted",
        "cancelled": "danger",
        "declined": "danger",
        "manual_review": "warning",
        "pending": "warning",
        "pending_acceptance": "warning",
        "submitted": "info",
        "contacted": "info",
        "unassigned": "warning",
    }
    return mapping.get(str(value), "muted")


@register.filter
def audit_event_label(value: str) -> str:
    """Turn stored machine-friendly action names into readable labels."""

    return str(value or "").replace("_", " ").strip().title()
