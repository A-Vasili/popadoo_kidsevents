from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configure profile signals and role-group bootstrapping."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self) -> None:
        # Importing signals here ensures they are registered once Django is ready.
        from . import signals  # noqa: F401
