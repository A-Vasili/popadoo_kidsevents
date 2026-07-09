# This file contains the apps code used by the operations part of the project.
# Comments in this file explain the purpose of each section without changing how the program works.

from django.apps import AppConfig


class OperationsConfig(AppConfig):
    """Staff scheduling, assignment, and owner-panel application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "operations"
