from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path("", views.OperationsDashboardView.as_view(), name="operations_dashboard"),
    path(
        "assignments/",
        views.WorkerAssignmentListView.as_view(),
        name="operations_worker_assignments",
    ),
    path(
        "assignments/<int:pk>/",
        views.WorkerAssignmentDetailView.as_view(),
        name="operations_worker_assignment_detail",
    ),
    path(
        "assignments/<int:pk>/accept/",
        views.WorkerAssignmentAcceptView.as_view(),
        name="operations_worker_assignment_accept",
    ),
    path(
        "assignments/<int:pk>/decline/",
        views.WorkerAssignmentDeclineView.as_view(),
        name="operations_worker_assignment_decline",
    ),
    path(
        "profile/",
        views.WorkerProfileView.as_view(),
        name="operations_worker_profile",
    ),
    path(
        "availability/",
        views.WorkerAvailabilityView.as_view(),
        name="operations_worker_availability",
    ),
    path(
        "availability/<int:pk>/delete/",
        views.WorkerAvailabilityDeleteView.as_view(),
        name="operations_worker_availability_delete",
    ),
    path(
        "schedule/",
        views.WorkerScheduleView.as_view(),
        name="operations_worker_schedule",
    ),
    path("owner/workers/", views.OwnerWorkersView.as_view(), name="operations_owner_workers"),
    path(
        "owner/workers/<int:user_id>/permissions/",
        views.OwnerWorkerPermissionView.as_view(),
        name="operations_owner_worker_permissions",
    ),
    path("owner/schedule/", views.OwnerScheduleView.as_view(), name="operations_owner_schedule"),
    path(
        "owner/bookings/<int:booking_id>/assign/",
        views.OwnerManualAssignmentView.as_view(),
        name="operations_owner_manual_assignment",
    ),
    path("owner/pricing/", views.OwnerPricingView.as_view(), name="operations_owner_pricing"),
    path("owner/audit/", views.OwnerAuditView.as_view(), name="operations_owner_audit"),
]
