# This file controls how account profile records appear in Django administration.
# Comments in this file explain the purpose of each section without changing how the program works.

from django.contrib import admin

from .models import CustomerProfile, WorkerProfile


# This class controls how customer profile information appears in Django administration.
@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "preferred_language", "updated_at")
    search_fields = ("user__username", "user__email", "phone")
    list_filter = ("preferred_language",)


# This class controls how worker profile information appears in Django administration.
@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "is_active_worker", "max_daily_parties")
    list_filter = ("is_active_worker",)
    search_fields = ("user__username", "user__email", "display_name", "phone")
    list_editable = ("is_active_worker", "max_daily_parties")
