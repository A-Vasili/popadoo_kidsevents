from django.contrib import admin

from .models import AuditEvent, PartyAssignment, WorkerAvailability


@admin.register(WorkerAvailability)
class WorkerAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("worker", "availability_type", "start_at", "end_at")
    list_filter = ("availability_type", "start_at")
    search_fields = ("worker__display_name", "worker__user__username", "notes")
    date_hierarchy = "start_at"


@admin.register(PartyAssignment)
class PartyAssignmentAdmin(admin.ModelAdmin):
    list_display = ("party_build", "worker", "status", "assignment_source", "assigned_at")
    list_filter = ("status", "assignment_source", "assigned_at")
    search_fields = (
        "party_build__public_id",
        "party_build__contact_name",
        "worker__display_name",
        "worker__user__username",
    )
    readonly_fields = ("assigned_at", "responded_at")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "actor", "summary", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("summary", "actor__username", "object_id")
    readonly_fields = (
        "actor",
        "event_type",
        "object_type",
        "object_id",
        "summary",
        "before_data",
        "after_data",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
