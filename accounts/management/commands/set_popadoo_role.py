
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from accounts.models import WorkerProfile
from accounts.permissions import OWNER_GROUP, PRICING_GROUP, WORKER_GROUP


class Command(BaseCommand):
    """Local administration helper for assigning an existing account's role."""

    help = "Assign an existing user to customer, worker, pricing-manager, or owner role."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument(
            "role",
            choices=("customer", "worker", "pricing-manager", "owner"),
        )

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist as exc:
            raise CommandError("No user exists with that username.") from exc

        role = options["role"]
        owners, _ = Group.objects.get_or_create(name=OWNER_GROUP)
        workers, _ = Group.objects.get_or_create(name=WORKER_GROUP)
        pricing, _ = Group.objects.get_or_create(name=PRICING_GROUP)

        owners.user_set.remove(user)
        workers.user_set.remove(user)
        pricing.user_set.remove(user)

        profile = getattr(user, "worker_profile", None)
        if profile:
            profile.is_active_worker = False
            profile.save(update_fields=["is_active_worker", "updated_at"])

        if role == "owner":
            owners.user_set.add(user)
        elif role in {"worker", "pricing-manager"}:
            workers.user_set.add(user)
            profile, _ = WorkerProfile.objects.get_or_create(user=user)
            profile.is_active_worker = True
            profile.save(update_fields=["is_active_worker", "updated_at"])
            if role == "pricing-manager":
                pricing.user_set.add(user)

        self.stdout.write(self.style.SUCCESS(f"{user.username} is now a {role}."))
