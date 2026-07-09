# This file controls worker and owner pages, including schedules, assignments, permissions, and pricing.
# Comments in this file explain the purpose of each section without changing how the program works.

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from accounts.models import WorkerProfile
from accounts.permissions import can_access_operations, can_manage_pricing, is_owner, is_worker
from party_builder.models import AddonExperience, GuestPriceTier, PartyBuild, PartyPackage

from .forms import (
    AddonPricingForm,
    DeclineAssignmentForm,
    GuestTierPricingForm,
    ManualAssignmentForm,
    PackagePricingForm,
    WorkerAvailabilityForm,
    WorkerProfileForm,
)
from .models import AuditEvent, PartyAssignment, WorkerAvailability
from .services.assignment import accept_assignment, assign_manually, decline_assignment
from .services.permissions import (
    demote_worker,
    grant_pricing_management,
    promote_to_worker,
    revoke_pricing_management,
)
from .services.scheduling import find_schedule_conflicts, get_event_window, worker_is_available


# This variable stores the active Django user model so the project remains compatible with Django settings.
User = get_user_model()


# This reusable mixin adds operations access behaviour to several views.
class OperationsAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    # This test checks that func.
    def test_func(self):
        return can_access_operations(self.request.user)


# This reusable mixin adds worker required behaviour to several views.
class WorkerRequiredMixin(OperationsAccessMixin):
    # This test checks that func.
    def test_func(self):
        return is_worker(self.request.user) or is_owner(self.request.user)

    # This method finds or prepares the worker profile needed by the rest of the code.
    def get_worker_profile(self):
        profile = getattr(self.request.user, "worker_profile", None)
        if profile is None and not is_owner(self.request.user):
            raise PermissionDenied("A worker profile is required.")
        return profile


# This reusable mixin adds owner required behaviour to several views.
class OwnerRequiredMixin(OperationsAccessMixin):
    # This test checks that func.
    def test_func(self):
        return is_owner(self.request.user)


# This reusable mixin adds pricing required behaviour to several views.
class PricingRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    # This test checks that func.
    def test_func(self):
        return can_manage_pricing(self.request.user)


# This view controls the operations dashboard page or action.
class OperationsDashboardView(OperationsAccessMixin, TemplateView):
    template_name = "operations/dashboard.html"

    # This method adds the information that the template needs to display the page.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["is_owner_panel"] = is_owner(user)
        if is_owner(user):
            context.update(
                {
                    "manual_review_bookings": PartyBuild.objects.filter(
                        assignment_state=PartyBuild.AssignmentState.MANUAL_REVIEW
                    ).select_related("package")[:10],
                    "pending_assignments": PartyAssignment.objects.filter(
                        status=PartyAssignment.Status.PENDING
                    ).select_related("party_build", "worker__user")[:10],
                    "upcoming_assignments": PartyAssignment.objects.filter(
                        status=PartyAssignment.Status.ACCEPTED,
                        party_build__event_date__gte=timezone.localdate(),
                    ).select_related("party_build", "worker__user")[:10],
                    "active_worker_count": WorkerProfile.objects.filter(
                        is_active_worker=True,
                        user__is_active=True,
                    ).count(),
                }
            )
        else:
            worker = self.get_worker_profile()
            context.update(
                {
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

    # This method finds or prepares the worker profile needed by the rest of the code.
    def get_worker_profile(self):
        return get_object_or_404(WorkerProfile, user=self.request.user, is_active_worker=True)


# This view controls the worker assignment list page or action.
class WorkerAssignmentListView(WorkerRequiredMixin, ListView):
    template_name = "operations/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 20

    # This method limits the database records to the ones the current user is allowed to see.
    def get_queryset(self):
        queryset = PartyAssignment.objects.select_related(
            "party_build__package", "worker__user"
        ).prefetch_related("party_build__addon_items__addon")
        if is_owner(self.request.user):
            return queryset
        return queryset.filter(worker=self.get_worker_profile())


# This view controls the worker assignment detail page or action.
class WorkerAssignmentDetailView(WorkerRequiredMixin, DetailView):
    model = PartyAssignment
    template_name = "operations/assignment_detail.html"
    context_object_name = "assignment"

    # This method limits the database records to the ones the current user is allowed to see.
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "party_build__package", "party_build__guest_tier", "worker__user"
        ).prefetch_related("party_build__addon_items__addon")
        if is_owner(self.request.user):
            return queryset
        return queryset.filter(worker=self.get_worker_profile())

    # This method adds the information that the template needs to display the page.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["decline_form"] = DeclineAssignmentForm()
        return context


# This view controls the worker assignment accept page or action.
class WorkerAssignmentAcceptView(WorkerRequiredMixin, View):
    http_method_names = ["post"]

    # This method processes a submitted form and performs the protected action requested by the user.
    def post(self, request, pk):
        worker = self.get_worker_profile()
        try:
            assignment = accept_assignment(assignment_id=pk, worker=worker, actor=request.user)
        except (ValidationError, PartyAssignment.DoesNotExist) as error:
            messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
            return redirect("operations:operations_worker_assignment_detail", pk=pk)
        messages.success(request, "The party is now confirmed in your schedule.")
        return redirect("operations:operations_worker_assignment_detail", pk=assignment.pk)


# This view controls the worker assignment decline page or action.
class WorkerAssignmentDeclineView(WorkerRequiredMixin, FormView):
    form_class = DeclineAssignmentForm
    template_name = "operations/assignment_detail.html"

    # This method performs setup and permission checks before the request reaches the page action.
    def dispatch(self, request, *args, **kwargs):
        self.assignment = get_object_or_404(PartyAssignment, pk=kwargs["pk"])
        if not is_owner(request.user) and self.assignment.worker_id != self.get_worker_profile().pk:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    # This method redisplays the page with helpful messages when the form contains errors.
    def form_invalid(self, form):
        context = {
            "assignment": self.assignment,
            "decline_form": form,
        }
        return self.render_to_response(context)

    # This method handles a correctly completed form and performs the requested action.
    def form_valid(self, form):
        worker = self.assignment.worker if is_owner(self.request.user) else self.get_worker_profile()
        try:
            decline_assignment(
                assignment_id=self.assignment.pk,
                worker=worker,
                reason=form.cleaned_data["reason"],
                actor=self.request.user,
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, "The assignment was declined and will be reassigned.")
        return redirect("operations:operations_worker_assignments")


class WorkerProfileView(WorkerRequiredMixin, FormView):
    """Worker-editable name and phone details used in staff operations."""

    template_name = "operations/worker_profile.html"
    form_class = WorkerProfileForm
    success_url = reverse_lazy("operations:operations_worker_profile")

    # This method finds or prepares the worker profile needed by the rest of the code.
    def get_worker_profile(self):
        return get_object_or_404(WorkerProfile, user=self.request.user, is_active_worker=True)

    # This method passes the extra information that the form needs when it is created.
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_worker_profile()
        return kwargs

    # This method handles a correctly completed form and performs the requested action.
    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Your worker profile was updated.")
        return super().form_valid(form)


# This view controls the worker availability page or action.
class WorkerAvailabilityView(WorkerRequiredMixin, FormView):
    template_name = "operations/availability.html"
    form_class = WorkerAvailabilityForm
    success_url = reverse_lazy("operations:operations_worker_availability")

    # This method finds or prepares the worker profile needed by the rest of the code.
    def get_worker_profile(self):
        return get_object_or_404(WorkerProfile, user=self.request.user, is_active_worker=True)

    # This method handles a correctly completed form and performs the requested action.
    def form_valid(self, form):
        availability = form.save(commit=False)
        availability.worker = self.get_worker_profile()
        availability.full_clean()
        availability.save()
        messages.success(self.request, "Your availability was saved.")
        return super().form_valid(form)

    # This method adds the information that the template needs to display the page.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["availability_periods"] = self.get_worker_profile().availability_periods.filter(
            end_at__gte=timezone.now()
        )
        return context


# This view controls the worker availability delete page or action.
class WorkerAvailabilityDeleteView(WorkerRequiredMixin, View):
    http_method_names = ["post"]

    # This method processes a submitted form and performs the protected action requested by the user.
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


# This view controls the worker schedule page or action.
class WorkerScheduleView(WorkerRequiredMixin, TemplateView):
    template_name = "operations/worker_schedule.html"

    # This method adds the information that the template needs to display the page.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        worker = self.get_worker_profile()
        context["worker"] = worker
        context["assignments"] = worker.assignments.filter(
            status=PartyAssignment.Status.ACCEPTED,
            party_build__event_date__gte=timezone.localdate(),
        ).select_related("party_build__package")
        return context


# This view controls the owner workers page or action.
class OwnerWorkersView(OwnerRequiredMixin, TemplateView):
    template_name = "operations/owner_workers.html"

    # This method adds the information that the template needs to display the page.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        users = User.objects.filter(is_superuser=False).prefetch_related("groups")
        if query:
            users = users.filter(
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
            )
        context["users"] = users.select_related("worker_profile") if hasattr(User, "worker_profile") else users
        context["query"] = query
        return context


# This view controls the owner worker permission page or action.
class OwnerWorkerPermissionView(OwnerRequiredMixin, View):
    http_method_names = ["post"]

    # This method processes a submitted form and performs the protected action requested by the user.
    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id, is_superuser=False)
        action = request.POST.get("action")
        try:
            if action == "promote":
                promote_to_worker(user, request.user)
                messages.success(request, f"{user} is now a worker.")
            elif action == "demote":
                demote_worker(user, request.user)
                messages.success(request, f"{user} is now a registered customer.")
            elif action == "grant_pricing":
                grant_pricing_management(user, request.user)
                messages.success(request, f"{user} can now manage pricing.")
            elif action == "revoke_pricing":
                revoke_pricing_management(user, request.user)
                messages.success(request, f"Pricing rights were removed from {user}.")
            else:
                messages.error(request, "Choose a valid permission action.")
        except (ValidationError, PermissionDenied) as error:
            messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
        return redirect("operations:operations_owner_workers")


# This view controls the owner schedule page or action.
class OwnerScheduleView(OwnerRequiredMixin, TemplateView):
    template_name = "operations/owner_schedule.html"

    # This method adds the information that the template needs to display the page.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workers"] = WorkerProfile.objects.filter(is_active_worker=True).select_related("user")
        context["assignments"] = PartyAssignment.objects.filter(
            status__in=(PartyAssignment.Status.PENDING, PartyAssignment.Status.ACCEPTED),
            party_build__event_date__gte=timezone.localdate(),
        ).select_related("worker__user", "party_build__package")
        context["manual_review_bookings"] = PartyBuild.objects.filter(
            assignment_state=PartyBuild.AssignmentState.MANUAL_REVIEW
        ).select_related("package")
        context["availability_periods"] = WorkerAvailability.objects.filter(
            end_at__gte=timezone.now()
        ).select_related("worker__user")[:100]
        return context


# This view controls the owner manual assignment page or action.
class OwnerManualAssignmentView(OwnerRequiredMixin, FormView):
    template_name = "operations/manual_assignment.html"
    form_class = ManualAssignmentForm

    # This method performs setup and permission checks before the request reaches the page action.
    def dispatch(self, request, *args, **kwargs):
        self.party_build = get_object_or_404(
            PartyBuild.objects.select_related("package").prefetch_related("addon_items__addon"),
            pk=kwargs["booking_id"],
        )
        return super().dispatch(request, *args, **kwargs)

    # This method adds the information that the template needs to display the page.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["party_build"] = self.party_build
        event_window = get_event_window(self.party_build)
        worker_rows = []
        for worker in WorkerProfile.objects.filter(is_active_worker=True).select_related("user"):
            conflicts = find_schedule_conflicts(worker, *event_window) if event_window else []
            available = worker_is_available(worker, *event_window) if event_window else False
            worker_rows.append(
                {
                    "worker": worker,
                    "conflicts": conflicts,
                    "available": available,
                }
            )
        context["worker_rows"] = worker_rows
        return context

    # This method handles a correctly completed form and performs the requested action.
    def form_valid(self, form):
        try:
            assignment = assign_manually(
                party_build=self.party_build,
                worker=form.cleaned_data["worker"],
                owner=self.request.user,
                override_reason=form.cleaned_data.get("override_reason", ""),
                already_agreed=form.cleaned_data.get("already_agreed", False),
            )
        except ValidationError as error:
            form.add_error("override_reason", error)
            return self.form_invalid(form)
        messages.success(self.request, "The manual assignment was saved.")
        return redirect("operations:operations_worker_assignment_detail", pk=assignment.pk)


class OwnerAuditView(OwnerRequiredMixin, ListView):
    """Read-only history of role, pricing, and assignment actions."""

    model = AuditEvent
    template_name = "operations/audit.html"
    context_object_name = "events"
    paginate_by = 50

    # This method limits the database records to the ones the current user is allowed to see.
    def get_queryset(self):
        return AuditEvent.objects.select_related("actor")


# This view controls the owner pricing page or action.
class OwnerPricingView(PricingRequiredMixin, TemplateView):
    template_name = "operations/pricing.html"

    # This method adds the information that the template needs to display the page.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["packages"] = PartyPackage.objects.prefetch_related("guest_price_tiers")
        context["addons"] = AddonExperience.objects.all()
        context["addon_create_form"] = kwargs.get("addon_create_form", AddonPricingForm(prefix="new"))
        return context

    # This method processes a submitted form and performs the protected action requested by the user.
    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")
        try:
            if action == "update_package":
                instance = get_object_or_404(PartyPackage, pk=request.POST.get("object_id"))
                form = PackagePricingForm(request.POST, instance=instance, prefix=f"package-{instance.pk}")
            elif action == "update_tier":
                instance = get_object_or_404(GuestPriceTier, pk=request.POST.get("object_id"))
                form = GuestTierPricingForm(request.POST, instance=instance, prefix=f"tier-{instance.pk}")
            elif action == "create_addon":
                form = AddonPricingForm(request.POST, prefix="new")
                instance = None
            elif action == "update_addon":
                instance = get_object_or_404(AddonExperience, pk=request.POST.get("object_id"))
                form = AddonPricingForm(request.POST, instance=instance, prefix=f"addon-{instance.pk}")
            else:
                messages.error(request, "Choose a valid pricing action.")
                return redirect("operations:operations_owner_pricing")

            if form.is_valid():
                before = {}
                if instance:
                    before = {field: str(getattr(instance, field)) for field in form.changed_data}
                saved = form.save()
                AuditEvent.objects.create(
                    actor=request.user,
                    event_type="pricing_changed",
                    object_type=saved.__class__.__name__,
                    object_id=str(saved.pk),
                    summary=f"{request.user} updated {saved}.",
                    before_data=before,
                    after_data={field: str(getattr(saved, field)) for field in form.changed_data},
                )
                messages.success(request, "Pricing information was saved.")
                return redirect("operations:operations_owner_pricing")

            messages.error(request, "Please correct the pricing form errors.")
            context = self.get_context_data(addon_create_form=form if action == "create_addon" else None)
            context["invalid_form"] = form
            context["invalid_action"] = action
            context["invalid_object_id"] = request.POST.get("object_id")
            return self.render_to_response(context)
        except (ValidationError, ValueError) as error:
            messages.error(request, str(error))
            return redirect("operations:operations_owner_pricing")
