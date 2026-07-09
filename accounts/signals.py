from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import CustomerProfile
from .permissions import OWNER_GROUP, PRICING_GROUP, WORKER_GROUP


@receiver(post_save, sender=get_user_model())
def ensure_customer_profile(sender, instance, created, **kwargs):
    """Every account receives an autofill profile, including staff accounts."""

    if created:
        CustomerProfile.objects.get_or_create(user=instance)


ROLE_PERMISSION_CODENAMES = {
    OWNER_GROUP: {
        "manage_worker_roles",
        "manage_pricing_rights",
        "view_all_worker_schedules",
        "view_all_schedules",
        "manually_assign_party",
        "manage_all_availability",
        "add_partypackage",
        "change_partypackage",
        "view_partypackage",
        "add_guestpricetier",
        "change_guestpricetier",
        "view_guestpricetier",
        "add_addonexperience",
        "change_addonexperience",
        "view_addonexperience",
        "view_partybuild",
        "change_partybuild",
        "view_partyassignment",
        "change_partyassignment",
        "add_partyassignment",
        "view_workeravailability",
        "change_workeravailability",
        "add_workeravailability",
        "delete_workeravailability",
        "view_auditevent",
    },
    WORKER_GROUP: {
        "view_partyassignment",
        "change_partyassignment",
        "view_workeravailability",
        "change_workeravailability",
        "add_workeravailability",
        "delete_workeravailability",
    },
    PRICING_GROUP: {
        "add_partypackage",
        "change_partypackage",
        "view_partypackage",
        "add_guestpricetier",
        "change_guestpricetier",
        "view_guestpricetier",
        "add_addonexperience",
        "change_addonexperience",
        "view_addonexperience",
    },
}


@receiver(post_migrate)
def ensure_role_groups(sender, **kwargs):
    """Create business groups and attach permissions after every migration run."""

    for group_name, codenames in ROLE_PERMISSION_CODENAMES.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        permissions = Permission.objects.filter(codename__in=codenames)
        group.permissions.add(*permissions)
