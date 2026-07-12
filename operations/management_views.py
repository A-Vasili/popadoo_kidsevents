"""Views for Popadoo's custom management panel.

The management interface is intentionally separate from the public website and
from the worker portal. Views stay focused on request handling while role,
archive, assignment, and audit rules remain in reusable services.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import CharField, Count, Prefetch, Q
from django.db.models.functions import Cast
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from accounts.models import WorkerProfile
from accounts.permissions import (
    OWNER_GROUP,
    PRICING_GROUP,
    WORKER_GROUP,
    can_manage_pricing,
    is_owner,
)
from party_builder.models import AddonExperience, Category, GuestPriceTier, PartyBuild, PartyPackage

from .forms import (
    ManualAssignmentForm,
    ActionConfirmationForm,
    AddonForm,
    BookingStatusForm,
    CategoryForm,
    GuestPriceTierForm,
    ManagedUserForm,
    OwnerWorkerCreationForm,
    ManualReviewForm,
    PackageForm,
)
from .models import AuditEvent, PartyAssignment, WorkerAvailability
from .services.assignment import assign_manually
from .services.audit import model_snapshot, record_audit
from .services.bookings import change_booking_status, send_to_manual_review
from .services.catalogue import (
    remove_addon,
    remove_category,
    remove_package,
    remove_tier,
    save_catalogue_form,
)
from .services.scheduling import find_schedule_conflicts, get_event_window, worker_is_available
from .services.users import (
    demote_worker,
    ensure_owner_can_manage,
    grant_pricing_management,
    promote_to_worker,
    revoke_pricing_management,
    set_account_active,
)

User = get_user_model()


class ManagementContextMixin:
    """Supply page title, active navigation, breadcrumbs, and filter links."""

    page_title = "Management"
    active_section = "dashboard"
    breadcrumbs: tuple[tuple[str, str | None], ...] = ()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.copy()
        query.pop("page", None)
        resolved_breadcrumbs = []
        for label, target in self.breadcrumbs:
            if target and not target.startswith("/"):
                target = reverse(target)
            resolved_breadcrumbs.append((label, target))
        context.update(
            {
                "management_page_title": self.page_title,
                "management_active_section": self.active_section,
                "management_breadcrumbs": tuple(resolved_breadcrumbs),
                "pagination_query": query.urlencode(),
            }
        )
        return context


class OwnerManagementMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Permit owners and superusers; authenticated failures receive HTTP 403."""

    raise_exception = True

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(
                self.request.get_full_path(),
                self.get_login_url(),
                self.get_redirect_field_name(),
            )
        raise PermissionDenied

    def test_func(self):
        return is_owner(self.request.user)


class CatalogueManagementMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Permit owners and workers who were explicitly delegated pricing access."""

    raise_exception = True

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(
                self.request.get_full_path(),
                self.get_login_url(),
                self.get_redirect_field_name(),
            )
        raise PermissionDenied

    def test_func(self):
        return can_manage_pricing(self.request.user)


class ManagementDashboardView(OwnerManagementMixin, ManagementContextMixin, TemplateView):
    template_name = "operations/management/dashboard.html"
    page_title = "Management dashboard"
    active_section = "dashboard"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        week_end = today + timedelta(days=7)
        attention = PartyBuild.objects.filter(
            Q(assignment_state__in=(PartyBuild.AssignmentState.UNASSIGNED, PartyBuild.AssignmentState.MANUAL_REVIEW))
            | Q(status=PartyBuild.Status.SUBMITTED)
        ).select_related("package").order_by("event_date")
        upcoming = PartyBuild.objects.filter(
            event_date__gte=today,
            event_date__lte=week_end,
        ).select_related("package").prefetch_related(
            Prefetch(
                "assignments",
                queryset=PartyAssignment.objects.filter(status=PartyAssignment.Status.ACCEPTED).select_related("worker__user"),
                to_attr="accepted_assignments_for_dashboard",
            )
        ).order_by("event_date", "event_time")
        context.update(
            {
                "stats": {
                    "active_packages": PartyPackage.objects.filter(is_active=True).count(),
                    "active_addons": AddonExperience.objects.filter(is_active=True).count(),
                    "active_categories": Category.objects.filter(is_active=True).count(),
                    "upcoming_week": PartyBuild.objects.filter(event_date__gte=today, event_date__lte=week_end).count(),
                    "unassigned": PartyBuild.objects.filter(assignment_state=PartyBuild.AssignmentState.UNASSIGNED).count(),
                    "manual_review": PartyBuild.objects.filter(assignment_state=PartyBuild.AssignmentState.MANUAL_REVIEW).count(),
                    "active_workers": WorkerProfile.objects.filter(is_active_worker=True, user__is_active=True).count(),
                    "pending_offers": PartyAssignment.objects.filter(status=PartyAssignment.Status.PENDING).count(),
                },
                "attention_bookings": attention[:8],
                "upcoming_bookings": upcoming[:8],
                "recent_catalogue_events": AuditEvent.objects.filter(
                    Q(event_type__contains="package")
                    | Q(event_type__contains="addon")
                    | Q(event_type__contains="category")
                    | Q(event_type__contains="tier")
                    | Q(event_type="catalogue_image_changed")
                ).select_related("actor")[:8],
                "recent_audit_events": AuditEvent.objects.select_related("actor")[:8],
            }
        )
        return context


class CatalogueIndexView(CatalogueManagementMixin, ManagementContextMixin, TemplateView):
    template_name = "operations/management/catalogue/index.html"
    page_title = "Catalogue"
    active_section = "catalogue"
    breadcrumbs = (("Catalogue", None),)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "package_count": PartyPackage.objects.count(),
                "tier_count": GuestPriceTier.objects.count(),
                "addon_count": AddonExperience.objects.count(),
                "category_count": Category.objects.count(),
            }
        )
        return context


class CategoryListView(CatalogueManagementMixin, ManagementContextMixin, ListView):
    template_name = "operations/management/categories/list.html"
    context_object_name = "categories"
    paginate_by = 20
    page_title = "Categories"
    active_section = "categories"
    breadcrumbs = (("Categories", None),)

    ORDERING = {
        "order": ("display_order", "name"),
        "name": ("name",),
        "-name": ("-name",),
        "newest": ("-created_at",),
    }

    def get_queryset(self):
        queryset = Category.objects.select_related("parent").annotate(
            package_count=Count("packages", distinct=True),
            addon_count=Count("addons", distinct=True),
        )
        query = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "")
        kind = self.request.GET.get("kind", "")
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(slug__icontains=query) | Q(description__icontains=query))
        if status in {"active", "inactive"}:
            queryset = queryset.filter(is_active=(status == "active"))
        if kind == "main":
            queryset = queryset.filter(parent__isnull=True)
        elif kind == "sub":
            queryset = queryset.filter(parent__isnull=False)
        return queryset.order_by(*self.ORDERING.get(self.request.GET.get("ordering", "order"), self.ORDERING["order"]))


class CategoryDetailView(CatalogueManagementMixin, ManagementContextMixin, DetailView):
    model = Category
    template_name = "operations/management/categories/detail.html"
    context_object_name = "category"
    page_title = "Category details"
    active_section = "categories"

    def get_queryset(self):
        return Category.objects.select_related("parent").prefetch_related("children", "packages", "addons")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["management_breadcrumbs"] = (("Categories", reverse("management:management_category_list")), (self.object.name, None))
        return context


class CatalogueFormView(CatalogueManagementMixin, ManagementContextMixin, FormView):
    """Reusable create/edit workflow for catalogue records."""

    model = None
    success_name = ""
    object_label = "record"
    template_name = "operations/management/catalogue/form.html"
    object = None

    def dispatch(self, request, *args, **kwargs):
        pk = kwargs.get("pk")
        if pk:
            self.object = get_object_or_404(self.model, pk=pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.object
        kwargs["files"] = self.request.FILES or None
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "object": self.object,
                "object_label": self.object_label,
                "is_create": self.object is None,
                "cancel_url": reverse(self.success_name),
            }
        )
        return context

    def form_valid(self, form):
        try:
            saved = save_catalogue_form(form, actor=self.request.user)
        except ValidationError as error:
            # A service-level rule can involve several records, so it is shown
            # as a clear form-wide error while preserving every submitted value.
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, f"{saved} was saved successfully.")
        return redirect(self.success_name)


class CategoryCreateView(CatalogueFormView):
    model = Category
    form_class = CategoryForm
    success_name = "management:management_category_list"
    object_label = "category"
    page_title = "Create category"
    active_section = "categories"
    breadcrumbs = (("Categories", "management:management_category_list"), ("Create", None))


class CategoryUpdateView(CategoryCreateView):
    page_title = "Edit category"


class CatalogueRemoveView(CatalogueManagementMixin, ManagementContextMixin, FormView):
    form_class = ActionConfirmationForm
    template_name = "operations/management/confirm_action.html"
    model = None
    remove_service = None
    success_name = ""
    object_label = "record"
    object = None

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(self.model, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "target": self.object,
                "target_name": str(self.object),
                "eyebrow": "Protected catalogue action",
                "will_archive": self.will_archive(),
                "usage_summary": self.usage_summary(),
                "action_label": ("Archive" if self.will_archive() else "Delete") + f" {self.object_label}",
                "title": ("Archive" if self.will_archive() else "Delete") + f" {self.object_label} “{self.object}”?",
                "consequence": (
                    "This record is referenced by existing catalogue or booking data. It will be deactivated instead of being destroyed, so historical bookings remain accurate."
                    if self.will_archive()
                    else "This record is unused and can be permanently deleted. This action cannot be undone."
                ),
                "cancel_url": reverse(self.success_name),
            }
        )
        return context

    def will_archive(self) -> bool:
        return False

    def usage_summary(self) -> str:
        return ""

    def form_valid(self, form):
        try:
            result = self.remove_service(self.object, actor=self.request.user)
        except ValidationError as error:
            # Deleting the last default package/tier would break checkout. Keep
            # the confirmation page open and explain the safe next step.
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, result.message)
        return redirect(self.success_name)


class CategoryRemoveView(CatalogueRemoveView):
    model = Category
    remove_service = staticmethod(remove_category)
    success_name = "management:management_category_list"
    object_label = "category"
    page_title = "Delete or deactivate category"
    active_section = "categories"

    def will_archive(self):
        return self.object.packages.exists() or self.object.addons.exists() or self.object.children.exists()

    def usage_summary(self):
        parts = []
        if self.object.packages.exists():
            parts.append(f"{self.object.packages.count()} package(s)")
        if self.object.addons.exists():
            parts.append(f"{self.object.addons.count()} add-on(s)")
        if self.object.children.exists():
            parts.append(f"{self.object.children.count()} subcategory record(s)")
        return ", ".join(parts)


class PackageListView(CatalogueManagementMixin, ManagementContextMixin, ListView):
    template_name = "operations/management/packages/list.html"
    context_object_name = "packages"
    paginate_by = 20
    page_title = "Packages"
    active_section = "catalogue"
    breadcrumbs = (("Catalogue", "management:management_catalogue"), ("Packages", None))

    ORDERING = {
        "order": ("display_order", "name"),
        "name": ("name",),
        "-name": ("-name",),
        "price": ("base_price", "name"),
        "-price": ("-base_price", "name"),
    }

    def get_queryset(self):
        queryset = PartyPackage.objects.select_related("category")
        query = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category", "")
        status = self.request.GET.get("status", "")
        default = self.request.GET.get("default", "")
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(slug__icontains=query) | Q(short_description__icontains=query))
        if category.isdigit():
            queryset = queryset.filter(category_id=category)
        if status in {"active", "inactive"}:
            queryset = queryset.filter(is_active=(status == "active"))
        if default in {"yes", "no"}:
            queryset = queryset.filter(is_default=(default == "yes"))
        return queryset.order_by(*self.ORDERING.get(self.request.GET.get("ordering", "order"), self.ORDERING["order"]))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_options"] = Category.objects.order_by("display_order", "name")
        return context


class PackageDetailView(CatalogueManagementMixin, ManagementContextMixin, DetailView):
    model = PartyPackage
    template_name = "operations/management/packages/detail.html"
    context_object_name = "package"
    page_title = "Package details"
    active_section = "catalogue"

    def get_queryset(self):
        return PartyPackage.objects.select_related("category").prefetch_related("guest_price_tiers")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["management_breadcrumbs"] = (("Catalogue", reverse("management:management_catalogue")), ("Packages", reverse("management:management_package_list")), (self.object.name, None))
        return context


class PackageCreateView(CatalogueFormView):
    model = PartyPackage
    form_class = PackageForm
    success_name = "management:management_package_list"
    object_label = "package"
    page_title = "Create package"
    active_section = "catalogue"


class PackageUpdateView(PackageCreateView):
    page_title = "Edit package"


class PackageRemoveView(CatalogueRemoveView):
    model = PartyPackage
    remove_service = staticmethod(remove_package)
    success_name = "management:management_package_list"
    object_label = "package"
    page_title = "Delete or archive package"
    active_section = "catalogue"

    def will_archive(self):
        return self.object.builds.exists() or self.object.guest_price_tiers.filter(builds__isnull=False).exists()

    def usage_summary(self):
        count = self.object.builds.count()
        return f"{count} historical booking(s)" if count else "Historical tier references"


class TierListView(CatalogueManagementMixin, ManagementContextMixin, ListView):
    template_name = "operations/management/tiers/list.html"
    context_object_name = "tiers"
    paginate_by = 25
    page_title = "Guest-price tiers"
    active_section = "catalogue"

    def get_queryset(self):
        queryset = GuestPriceTier.objects.select_related("package")
        query = self.request.GET.get("q", "").strip()
        package = self.request.GET.get("package", "")
        status = self.request.GET.get("status", "")
        if query:
            queryset = queryset.filter(Q(label__icontains=query) | Q(package__name__icontains=query))
        if package.isdigit():
            queryset = queryset.filter(package_id=package)
        if status in {"active", "inactive"}:
            queryset = queryset.filter(is_active=(status == "active"))
        return queryset.order_by("package__display_order", "package__name", "display_order", "min_guests")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["package_options"] = PartyPackage.objects.order_by("display_order", "name")
        return context


class TierCreateView(CatalogueFormView):
    model = GuestPriceTier
    form_class = GuestPriceTierForm
    success_name = "management:management_tier_list"
    object_label = "guest-price tier"
    page_title = "Create guest-price tier"
    active_section = "catalogue"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        package_id = self.kwargs.get("package_id")
        if package_id:
            kwargs["package"] = get_object_or_404(PartyPackage, pk=package_id)
        return kwargs


class TierUpdateView(TierCreateView):
    page_title = "Edit guest-price tier"


class TierRemoveView(CatalogueRemoveView):
    model = GuestPriceTier
    remove_service = staticmethod(remove_tier)
    success_name = "management:management_tier_list"
    object_label = "guest-price tier"
    page_title = "Delete or archive guest-price tier"
    active_section = "catalogue"

    def will_archive(self):
        return self.object.builds.exists()

    def usage_summary(self):
        count = self.object.builds.count()
        return f"{count} historical booking(s)" if count else ""


class AddonListView(CatalogueManagementMixin, ManagementContextMixin, ListView):
    template_name = "operations/management/addons/list.html"
    context_object_name = "addons"
    paginate_by = 20
    page_title = "Add-ons"
    active_section = "catalogue"
    ORDERING = {
        "order": ("display_order", "name"),
        "name": ("name",),
        "-name": ("-name",),
        "price": ("price", "name"),
        "-price": ("-price", "name"),
    }

    def get_queryset(self):
        queryset = AddonExperience.objects.select_related("category")
        query = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category", "")
        status = self.request.GET.get("status", "")
        featured = self.request.GET.get("featured", "")
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(slug__icontains=query) | Q(short_description__icontains=query))
        if category.isdigit():
            queryset = queryset.filter(category_id=category)
        if status in {"active", "inactive"}:
            queryset = queryset.filter(is_active=(status == "active"))
        if featured in {"yes", "no"}:
            queryset = queryset.filter(is_featured=(featured == "yes"))
        return queryset.order_by(*self.ORDERING.get(self.request.GET.get("ordering", "order"), self.ORDERING["order"]))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_options"] = Category.objects.order_by("display_order", "name")
        return context


class AddonDetailView(CatalogueManagementMixin, ManagementContextMixin, DetailView):
    model = AddonExperience
    template_name = "operations/management/addons/detail.html"
    context_object_name = "addon"
    page_title = "Add-on details"
    active_section = "catalogue"

    def get_queryset(self):
        return AddonExperience.objects.select_related("category")


class AddonCreateView(CatalogueFormView):
    model = AddonExperience
    form_class = AddonForm
    success_name = "management:management_addon_list"
    object_label = "add-on"
    page_title = "Create add-on"
    active_section = "catalogue"


class AddonUpdateView(AddonCreateView):
    page_title = "Edit add-on"


class AddonRemoveView(CatalogueRemoveView):
    model = AddonExperience
    remove_service = staticmethod(remove_addon)
    success_name = "management:management_addon_list"
    object_label = "add-on"
    page_title = "Delete or archive add-on"
    active_section = "catalogue"

    def will_archive(self):
        return self.object.build_items.exists()

    def usage_summary(self):
        count = self.object.build_items.count()
        return f"{count} historical booking add-on selection(s)" if count else ""


class UserListView(OwnerManagementMixin, ManagementContextMixin, ListView):
    template_name = "operations/management/users/list.html"
    context_object_name = "managed_users"
    paginate_by = 25
    page_title = "Users and roles"
    active_section = "users"

    def get_queryset(self):
        # Superusers are never exposed to owner-level account management.
        base = User.objects.filter(is_superuser=False)
        # An owner may see their own record but not another owner's account.
        queryset = (
            base.exclude(groups__name=OWNER_GROUP)
            | base.filter(pk=self.request.user.pk)
        ).prefetch_related("groups").select_related("customer_profile", "worker_profile")
        query = self.request.GET.get("q", "").strip()
        role = self.request.GET.get("role", "")
        status = self.request.GET.get("status", "")
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
            )
        if role == "owner":
            queryset = queryset.filter(groups__name=OWNER_GROUP)
        elif role == "worker":
            queryset = queryset.filter(groups__name=WORKER_GROUP)
        elif role == "customer":
            queryset = queryset.exclude(groups__name__in=(OWNER_GROUP, WORKER_GROUP))
        if status in {"active", "inactive"}:
            queryset = queryset.filter(is_active=(status == "active"))
        return queryset.distinct().order_by("last_name", "first_name", "username")


class ProtectedUserObjectMixin:
    user_object = None

    def dispatch(self, request, *args, **kwargs):
        self.user_object = get_object_or_404(
            User.objects.filter(is_superuser=False).select_related("customer_profile", "worker_profile").prefetch_related("groups"),
            pk=kwargs["pk"],
        )
        if self.user_object.groups.filter(name=OWNER_GROUP).exists() and self.user_object.pk != request.user.pk:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class UserDetailView(ProtectedUserObjectMixin, OwnerManagementMixin, ManagementContextMixin, TemplateView):
    template_name = "operations/management/users/detail.html"
    page_title = "User details"
    active_section = "users"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.user_object
        context.update(
            {
                "managed_user": user,
                "customer_bookings": user.party_bookings.select_related("package")[:10],
                "worker_assignments": getattr(user, "worker_profile", None).assignments.select_related("party_build")[:10] if hasattr(user, "worker_profile") else [],
                "worker_availability": getattr(user, "worker_profile", None).availability_periods.all()[:10] if hasattr(user, "worker_profile") else [],
                "recent_events": AuditEvent.objects.filter(object_type="User", object_id=str(user.pk)).select_related("actor")[:10],
            }
        )
        return context


class UserUpdateView(ProtectedUserObjectMixin, OwnerManagementMixin, ManagementContextMixin, FormView):
    template_name = "operations/management/users/form.html"
    form_class = ManagedUserForm
    page_title = "Edit user profile"
    active_section = "users"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.user_object
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "managed_user": self.user_object,
                "form_eyebrow": "Account details",
                "form_title": f"Edit {self.user_object.get_full_name() or self.user_object.username}",
                "form_description": "Passwords and role permissions are managed separately and are never displayed here.",
                "submit_label": "Save user",
                "cancel_url": reverse("management:management_user_detail", args=[self.user_object.pk]),
            }
        )
        return context

    def form_valid(self, form):
        ensure_owner_can_manage(self.request.user, self.user_object)
        fields = ("first_name", "last_name", "email", "is_active")
        before = model_snapshot(self.user_object, fields)
        user = form.save()
        record_audit(
            actor=self.request.user,
            event_type="user_profile_updated",
            target=user,
            summary=f"{self.request.user} updated profile details for {user}.",
            before=before,
            after=model_snapshot(user, fields),
        )
        messages.success(self.request, "The user profile was updated.")
        return redirect("management:management_user_detail", pk=user.pk)


class UserCreateWorkerView(OwnerManagementMixin, ManagementContextMixin, FormView):
    template_name = "operations/management/users/form.html"
    form_class = OwnerWorkerCreationForm
    page_title = "Create worker account"
    active_section = "users"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form_eyebrow": "Staff account",
                "form_title": "Create worker",
                "form_description": "The worker receives staff portal access but no owner or administrator privileges.",
                "submit_label": "Create worker",
                "cancel_url": reverse("management:management_user_list"),
            }
        )
        return context

    def form_valid(self, form):
        user = form.save(actor=self.request.user)
        messages.success(self.request, f"Worker account {user.username} was created.")
        return redirect("management:management_user_detail", pk=user.pk)


class UserActionView(ProtectedUserObjectMixin, OwnerManagementMixin, ManagementContextMixin, FormView):
    template_name = "operations/management/confirm_action.html"
    form_class = ActionConfirmationForm
    page_title = "Confirm user action"
    active_section = "users"
    ACTION_LABELS = {
        "activate": "Activate account",
        "deactivate": "Deactivate account",
        "promote": "Promote to worker",
        "demote": "Demote to customer",
        "grant_pricing": "Grant pricing access",
        "revoke_pricing": "Revoke pricing access",
    }

    def dispatch(self, request, *args, **kwargs):
        self.action = kwargs["action"]
        if self.action not in self.ACTION_LABELS:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "target": self.user_object,
                "target_name": self.user_object.get_full_name() or self.user_object.username,
                "eyebrow": "Account security",
                "action_label": self.ACTION_LABELS[self.action],
                "title": f"{self.ACTION_LABELS[self.action]} for {self.user_object.get_full_name() or self.user_object.username}?",
                "consequence": self._consequence(),
                "cancel_url": reverse("management:management_user_detail", args=[self.user_object.pk]),
            }
        )
        return context

    def _consequence(self):
        return {
            "activate": "The user will be able to sign in again.",
            "deactivate": "The user will be signed out and unable to sign in until reactivated.",
            "promote": "The customer will gain access to the worker portal.",
            "demote": "Worker and pricing access will be removed; historical assignments remain.",
            "grant_pricing": "The worker will be able to manage catalogue and pricing records.",
            "revoke_pricing": "The worker will keep staff access but lose catalogue management access.",
        }[self.action]

    def form_valid(self, form):
        target = self.user_object
        try:
            if self.action == "activate":
                set_account_active(target=target, active=True, actor=self.request.user)
            elif self.action == "deactivate":
                set_account_active(target=target, active=False, actor=self.request.user)
            elif self.action == "promote":
                promote_to_worker(target, self.request.user)
            elif self.action == "demote":
                demote_worker(target, self.request.user)
            elif self.action == "grant_pricing":
                grant_pricing_management(target, self.request.user)
            else:
                revoke_pricing_management(target, self.request.user)
        except (PermissionDenied, ValidationError) as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, f"{self.ACTION_LABELS[self.action]} completed for {target}.")
        return redirect("management:management_user_detail", pk=target.pk)


class BookingListView(OwnerManagementMixin, ManagementContextMixin, ListView):
    template_name = "operations/management/bookings/list.html"
    context_object_name = "bookings"
    paginate_by = 25
    page_title = "Bookings"
    active_section = "bookings"

    def get_queryset(self):
        accepted = PartyAssignment.objects.filter(status=PartyAssignment.Status.ACCEPTED).select_related("worker__user")
        queryset = PartyBuild.objects.select_related("package", "guest_tier", "customer").prefetch_related(
            Prefetch("assignments", queryset=accepted, to_attr="accepted_assignments")
        ).annotate(public_id_text=Cast("public_id", output_field=CharField()))
        query = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "")
        assignment = self.request.GET.get("assignment", "")
        package = self.request.GET.get("package", "")
        worker = self.request.GET.get("worker", "")
        date_from = self.request.GET.get("date_from", "")
        date_to = self.request.GET.get("date_to", "")
        if query:
            queryset = queryset.filter(
                Q(contact_name__icontains=query)
                | Q(contact_email__icontains=query)
                | Q(public_id_text__icontains=query)
                | Q(event_address__icontains=query)
            )
        if status in PartyBuild.Status.values:
            queryset = queryset.filter(status=status)
        if assignment in PartyBuild.AssignmentState.values:
            queryset = queryset.filter(assignment_state=assignment)
        if package.isdigit():
            queryset = queryset.filter(package_id=package)
        if worker.isdigit():
            queryset = queryset.filter(assignments__worker_id=worker, assignments__status=PartyAssignment.Status.ACCEPTED)
        parsed_from = parse_date(date_from) if date_from else None
        parsed_to = parse_date(date_to) if date_to else None
        if parsed_from:
            queryset = queryset.filter(event_date__gte=parsed_from)
        if parsed_to:
            queryset = queryset.filter(event_date__lte=parsed_to)
        return queryset.distinct().order_by("event_date", "event_time", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "package_options": PartyPackage.objects.order_by("name"),
                "worker_options": WorkerProfile.objects.filter(is_active_worker=True).select_related("user"),
                "booking_status_choices": PartyBuild.Status.choices,
                "assignment_state_choices": PartyBuild.AssignmentState.choices,
            }
        )
        return context


class BookingDetailView(OwnerManagementMixin, ManagementContextMixin, DetailView):
    model = PartyBuild
    slug_field = "public_id"
    slug_url_kwarg = "public_id"
    template_name = "operations/management/bookings/detail.html"
    context_object_name = "booking"
    page_title = "Booking details"
    active_section = "bookings"

    def get_queryset(self):
        return PartyBuild.objects.select_related("package", "guest_tier", "customer").prefetch_related(
            "addon_items__addon",
            "assignments__worker__user",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "status_form": BookingStatusForm(booking=self.object),
                "manual_review_form": ManualReviewForm(),
                "audit_events": AuditEvent.objects.filter(object_type="PartyBuild", object_id=str(self.object.pk)).select_related("actor")[:15],
            }
        )
        return context


class BookingStatusUpdateView(OwnerManagementMixin, View):
    http_method_names = ["post"]

    def post(self, request, public_id):
        booking = get_object_or_404(PartyBuild, public_id=public_id)
        form = BookingStatusForm(request.POST, booking=booking)
        if form.is_valid():
            try:
                change_booking_status(
                    booking=booking,
                    status=form.cleaned_data["status"],
                    note=form.cleaned_data.get("note", ""),
                    actor=request.user,
                )
                messages.success(request, "The booking status was updated.")
            except ValidationError as error:
                messages.error(request, "; ".join(error.messages))
        else:
            messages.error(request, "The requested status change was not valid.")
        return redirect("management:management_booking_detail", public_id=booking.public_id)


class BookingManualReviewView(OwnerManagementMixin, View):
    http_method_names = ["post"]

    def post(self, request, public_id):
        booking = get_object_or_404(PartyBuild, public_id=public_id)
        form = ManualReviewForm(request.POST)
        if form.is_valid():
            send_to_manual_review(booking=booking, actor=request.user, reason=form.cleaned_data["reason"])
            messages.success(request, "The booking now requires manual review.")
        else:
            messages.error(request, "Explain why the booking needs manual review.")
        return redirect("management:management_booking_detail", public_id=booking.public_id)


class BookingAssignView(OwnerManagementMixin, ManagementContextMixin, FormView):
    template_name = "operations/management/bookings/assign.html"
    form_class = ManualAssignmentForm
    page_title = "Assign worker"
    active_section = "bookings"

    def dispatch(self, request, *args, **kwargs):
        self.booking = get_object_or_404(
            PartyBuild.objects.select_related("package").prefetch_related("addon_items__addon"),
            public_id=kwargs["public_id"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event_window = get_event_window(self.booking)
        worker_rows = []
        for worker in WorkerProfile.objects.filter(is_active_worker=True, user__is_active=True).select_related("user"):
            worker_rows.append(
                {
                    "worker": worker,
                    "available": worker_is_available(worker, *event_window) if event_window else False,
                    "conflicts": find_schedule_conflicts(worker, *event_window, exclude_build_id=self.booking.pk) if event_window else [],
                }
            )
        context.update({"booking": self.booking, "worker_rows": worker_rows})
        return context

    def form_valid(self, form):
        try:
            assign_manually(
                party_build=self.booking,
                worker=form.cleaned_data["worker"],
                owner=self.request.user,
                override_reason=form.cleaned_data.get("override_reason", ""),
                already_agreed=form.cleaned_data.get("already_agreed", False),
            )
        except ValidationError as error:
            form.add_error("override_reason", error)
            return self.form_invalid(form)
        messages.success(self.request, "The worker assignment was saved.")
        return redirect("management:management_booking_detail", public_id=self.booking.public_id)


class ScheduleView(OwnerManagementMixin, ManagementContextMixin, TemplateView):
    template_name = "operations/management/schedules.html"
    page_title = "Worker schedules"
    active_section = "schedules"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        requested_from = self.request.GET.get("date_from", "")
        requested_to = self.request.GET.get("date_to", "")
        parsed_from = parse_date(requested_from) or timezone.localdate()
        parsed_to = parse_date(requested_to) or (timezone.localdate() + timedelta(days=30))
        if parsed_to < parsed_from:
            parsed_to = parsed_from
        date_from = str(parsed_from)
        date_to = str(parsed_to)
        worker_id = self.request.GET.get("worker", "")
        assignments = PartyAssignment.objects.filter(
            status__in=(PartyAssignment.Status.PENDING, PartyAssignment.Status.ACCEPTED),
            party_build__event_date__gte=date_from,
            party_build__event_date__lte=date_to,
        ).select_related("worker__user", "party_build__package")
        availability = WorkerAvailability.objects.filter(
            end_at__date__gte=date_from,
            start_at__date__lte=date_to,
        ).select_related("worker__user")
        if worker_id.isdigit():
            assignments = assignments.filter(worker_id=worker_id)
            availability = availability.filter(worker_id=worker_id)
        context.update(
            {
                "assignments": assignments.order_by("party_build__event_date", "party_build__event_time"),
                "availability_periods": availability.order_by("start_at"),
                "workers": WorkerProfile.objects.filter(is_active_worker=True).select_related("user"),
                "date_from": date_from,
                "date_to": date_to,
            }
        )
        return context


class AuditListView(OwnerManagementMixin, ManagementContextMixin, ListView):
    template_name = "operations/management/audit/list.html"
    context_object_name = "events"
    paginate_by = 50
    page_title = "Audit history"
    active_section = "audit"

    def get_queryset(self):
        queryset = AuditEvent.objects.select_related("actor")
        query = self.request.GET.get("q", "").strip()
        event_type = self.request.GET.get("event_type", "").strip()
        actor = self.request.GET.get("actor", "")
        date_from = self.request.GET.get("date_from", "")
        date_to = self.request.GET.get("date_to", "")
        if query:
            queryset = queryset.filter(Q(summary__icontains=query) | Q(object_type__icontains=query) | Q(object_id__icontains=query))
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        if actor.isdigit():
            queryset = queryset.filter(actor_id=actor)
        parsed_from = parse_date(date_from) if date_from else None
        parsed_to = parse_date(date_to) if date_to else None
        if parsed_from:
            queryset = queryset.filter(created_at__date__gte=parsed_from)
        if parsed_to:
            queryset = queryset.filter(created_at__date__lte=parsed_to)
        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event_type_options"] = AuditEvent.objects.order_by("event_type").values_list("event_type", flat=True).distinct()
        context["actor_options"] = User.objects.filter(popadoo_audit_events__isnull=False).distinct().order_by("username")
        return context
