# This file contains the apps code used by the accounts part of the project.
# Comments in this file explain the purpose of each section without changing how the program works.

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configure profile signals and role-group bootstrapping."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    # This method runs after Django has loaded the application and connects its automatic setup tasks.
    def ready(self) -> None:
        # Importing signals here ensures they are registered once Django is ready.
        from . import signals  # noqa: F401
