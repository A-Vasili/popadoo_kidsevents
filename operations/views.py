"""Worker portal views and temporary redirects from retired owner pages.

Worker pages expose only the signed-in worker's records. Owner administration
lives under /management/ so the two private experiences remain clearly separate.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from accounts.models import WorkerProfile
from accounts.permissions import can_access_operations, is_owner, is_worker
from party_builder.models import PartyBuild

from .forms import (
    DeclineAssignmentForm,
    WorkerAvailabilityForm,
    WorkerProfileForm,
)
from .models import PartyAssignment, WorkerAvailability
from .services.assignment import accept_assignment, decline_assignment


class OperationsAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return can_access_operations(self.request.user)


class WorkerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return bool(is_worker(user) and not is_owner(user))

    def get_worker_profile(self):
        return get_object_or_404(
            WorkerProfile,
            user=self.request.user,
            is_active_worker=True,
        )


class OperationsDashboardView(OperationsAccessMixin, TemplateView):
    template_name = "operations/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and is_owner(request.user):
            return redirect("management:management_dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        worker = get_object_or_404(
            WorkerProfile,
            user=self.request.user,
            is_active_worker=True,
        )
        context.update(
            {
                "is_owner_panel": False,
                "pending_assignments": worker.assignments.filter(
                    status=PartyAssignment.Status.PENDING
                ).select_related("party_build__package")[:10],
                "upcoming_assignments": worker.assignments.filter(
                    status=PartyAssignment.Status.ACCEPTED,
                    party_build__event_date__gte=timezone.localdate(),
                ).select_related("party_build__package")[:10],
            }
        )
        return context


class WorkerAssignmentListView(WorkerRequiredMixin, ListView):
    template_name = "operations/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 20

    def get_queryset(self):
        return PartyAssignment.objects.filter(
            worker=self.get_worker_profile()
        ).select_related(
            "party_build__package", "worker__user"
        ).prefetch_related("party_build__addon_items__addon")


class WorkerAssignmentDetailView(WorkerRequiredMixin, DetailView):
    model = PartyAssignment
    template_name = "operations/assignment_detail.html"
    context_object_name = "assignment"

    def get_queryset(self):
        return PartyAssignment.objects.filter(
            worker=self.get_worker_profile()
        ).select_related(
            "party_build__package", "party_build__guest_tier", "worker__user"
        ).prefetch_related("party_build__addon_items__addon")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["decline_form"] = DeclineAssignmentForm()
        return context


class WorkerAssignmentAcceptView(WorkerRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        try:
            assignment = accept_assignment(
                assignment_id=pk,
                worker=self.get_worker_profile(),
                actor=request.user,
            )
        except (ValidationError, PartyAssignment.DoesNotExist) as error:
            messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
            return redirect("operations:operations_worker_assignment_detail", pk=pk)
        messages.success(request, "The party is now confirmed in your schedule.")
        return redirect("operations:operations_worker_assignment_detail", pk=assignment.pk)


class WorkerAssignmentDeclineView(WorkerRequiredMixin, FormView):
    form_class = DeclineAssignmentForm
    template_name = "operations/assignment_detail.html"

    def dispatch(self, request, *args, **kwargs):
        self.assignment = get_object_or_404(
            PartyAssignment,
            pk=kwargs["pk"],
            worker=self.get_worker_profile(),
        )
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        return self.render_to_response(
            {"assignment": self.assignment, "decline_form": form}
        )

    def form_valid(self, form):
        try:
            decline_assignment(
                assignment_id=self.assignment.pk,
                worker=self.get_worker_profile(),
                reason=form.cleaned_data["reason"],
                actor=self.request.user,
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, "The assignment was declined and will be reassigned.")
        return redirect("operations:operations_worker_assignments")


class WorkerProfileView(WorkerRequiredMixin, FormView):
    template_name = "operations/worker_profile.html"
    form_class = WorkerProfileForm
    success_url = reverse_lazy("operations:operations_worker_profile")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_worker_profile()
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Your worker profile was updated.")
        return super().form_valid(form)


class WorkerAvailabilityView(WorkerRequiredMixin, FormView):
    template_name = "operations/availability.html"
    form_class = WorkerAvailabilityForm
    success_url = reverse_lazy("operations:operations_worker_availability")

    def form_valid(self, form):
        availability = form.save(commit=False)
        availability.worker = self.get_worker_profile()
        availability.full_clean()
        availability.save()
        messages.success(self.request, "Your availability was saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["availability_periods"] = self.get_worker_profile().availability_periods.filter(
            end_at__gte=timezone.now()
        )
        return context


class WorkerAvailabilityDeleteView(WorkerRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        period = get_object_or_404(
            WorkerAvailability,
            pk=pk,
            worker=self.get_worker_profile(),
            start_at__gte=timezone.now(),
        )
        period.delete()
        messages.success(request, "The availability period was removed.")
        return redirect("operations:operations_worker_availability")


class WorkerScheduleView(WorkerRequiredMixin, TemplateView):
    template_name = "operations/worker_schedule.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        worker = self.get_worker_profile()
        context["worker"] = worker
        context["assignments"] = worker.assignments.filter(
            status=PartyAssignment.Status.ACCEPTED,
            party_build__event_date__gte=timezone.localdate(),
        ).select_related("party_build__package")
        return context


class LegacyOwnerBookingAssignmentRedirectView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Translate the old integer booking URL to the canonical UUID route."""

    raise_exception = True

    def test_func(self):
        return is_owner(self.request.user)

    def get(self, request, booking_id):
        booking = get_object_or_404(PartyBuild, pk=booking_id)
        return redirect(
            "management:management_booking_assign",
            public_id=booking.public_id,
            permanent=True,
        )
