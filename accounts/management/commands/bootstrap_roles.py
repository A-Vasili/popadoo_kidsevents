
from django.core.management.base import BaseCommand

from accounts.signals import ensure_role_groups


class Command(BaseCommand):
    help = "Create Popadoo role groups and attach their Django permissions."

    def handle(self, *args, **options):
        ensure_role_groups(sender=None)
        self.stdout.write(self.style.SUCCESS("Popadoo role groups are ready."))
