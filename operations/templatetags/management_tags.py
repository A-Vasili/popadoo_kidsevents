"""Small presentation helpers for the custom management templates."""

from django import template

from accounts.permissions import OWNER_GROUP, PRICING_GROUP, WORKER_GROUP

register = template.Library()


@register.filter
def in_group(user, group_name: str) -> bool:
    return bool(getattr(user, "is_authenticated", False) and user.groups.filter(name=group_name).exists())


@register.filter
def management_role(user) -> str:
    if getattr(user, "is_superuser", False):
        return "Administrator"
    if user.groups.filter(name=OWNER_GROUP).exists():
        return "Owner"
    if user.groups.filter(name=WORKER_GROUP).exists():
        return "Worker"
    return "Customer"


@register.filter
def has_pricing_access(user) -> bool:
    return user.groups.filter(name=PRICING_GROUP).exists()


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
