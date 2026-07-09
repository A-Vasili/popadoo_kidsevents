# This file contains the apps code used by the party builder part of the project.
# Comments in this file explain the purpose of each section without changing how the program works.

from django.apps import AppConfig


class PartyBuilderConfig(AppConfig):
    """Application configuration for the custom party builder."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "party_builder"
    verbose_name = "Party Builder"
