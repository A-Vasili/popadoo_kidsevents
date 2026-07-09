# This file contains the bootstrap roles code used by the commands part of the project.
# Comments in this file explain the purpose of each section without changing how the program works.

from django.core.management.base import BaseCommand

from accounts.signals import ensure_role_groups


# This command lets a developer perform this setup task from the terminal.
class Command(BaseCommand):
    help = "Create Popadoo role groups and attach their Django permissions."

    # This method runs the command after Django has read and checked the terminal arguments.
    def handle(self, *args, **options):
        ensure_role_groups(sender=None)
        self.stdout.write(self.style.SUCCESS("Popadoo role groups are ready."))
