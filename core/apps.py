# This file contains the apps code used by the core part of the project.
# Comments in this file explain the purpose of each section without changing how the program works.

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
