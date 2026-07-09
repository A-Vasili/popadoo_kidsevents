from django.apps import AppConfig


class PartyBuilderConfig(AppConfig):
    """Application configuration for the custom party builder."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "party_builder"
    verbose_name = "Party Builder"
