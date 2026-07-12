"""Worker portal routes and temporary redirects from retired owner pages."""

from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "operations"

urlpatterns = [
    path("", views.OperationsDashboardView.as_view(), name="operations_dashboard"),
    path("assignments/", views.WorkerAssignmentListView.as_view(), name="operations_worker_assignments"),
    path("assignments/<int:pk>/", views.WorkerAssignmentDetailView.as_view(), name="operations_worker_assignment_detail"),
    path("assignments/<int:pk>/accept/", views.WorkerAssignmentAcceptView.as_view(), name="operations_worker_assignment_accept"),
    path("assignments/<int:pk>/decline/", views.WorkerAssignmentDeclineView.as_view(), name="operations_worker_assignment_decline"),
    path("profile/", views.WorkerProfileView.as_view(), name="operations_worker_profile"),
    path("availability/", views.WorkerAvailabilityView.as_view(), name="operations_worker_availability"),
    path("availability/<int:pk>/delete/", views.WorkerAvailabilityDeleteView.as_view(), name="operations_worker_availability_delete"),
    path("schedule/", views.WorkerScheduleView.as_view(), name="operations_worker_schedule"),

    # These GET-only names keep old bookmarks working while one management
    # interface remains authoritative for every owner action.
    path(
        "owner/workers/",
        RedirectView.as_view(pattern_name="management:management_user_list", permanent=True),
        name="operations_owner_workers",
    ),
    path(
        "owner/workers/create/",
        RedirectView.as_view(pattern_name="management:management_user_create_worker", permanent=True),
        name="operations_owner_worker_create",
    ),
    path(
        "owner/schedule/",
        RedirectView.as_view(pattern_name="management:management_schedule", permanent=True),
        name="operations_owner_schedule",
    ),
    path(
        "owner/pricing/",
        RedirectView.as_view(pattern_name="management:management_catalogue", permanent=True),
        name="operations_owner_pricing",
    ),
    path(
        "owner/audit/",
        RedirectView.as_view(pattern_name="management:management_audit", permanent=True),
        name="operations_owner_audit",
    ),
    path(
        "owner/bookings/<int:booking_id>/assign/",
        views.LegacyOwnerBookingAssignmentRedirectView.as_view(),
        name="operations_owner_manual_assignment",
    ),
]
