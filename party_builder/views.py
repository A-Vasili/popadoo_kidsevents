# This file controls the multi-step party builder, checkout, and confirmation pages.
# Comments in this file explain the purpose of each section without changing how the program works.

from __future__ import annotations

from datetime import date, time
from typing import Any

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, FormView

from .forms import PackageOptionsForm, PartyDetailsForm, SimulatedPaymentForm
from .models import AddonExperience, GuestPriceTier, PartyBuild, PartyPackage
from .services import calculate_party_quote, create_completed_party_build


CHECKOUT_SESSION_KEY = "party_builder_checkout"
AUTHORIZED_BUILD_SESSION_KEY = "party_builder_builds"


class CheckoutStateMixin:
    """Shared session and catalogue helpers for the three checkout steps."""

    package: PartyPackage

    def dispatch(self, request, *args, **kwargs):
        self.package = self.get_package()
        return super().dispatch(request, *args, **kwargs)

    # This method finds or prepares the package needed by the rest of the code.
    def get_package(self) -> PartyPackage:
        package = (
            PartyPackage.objects.filter(is_active=True, is_default=True).first()
            or PartyPackage.objects.filter(is_active=True).first()
        )
        if package is None:
            raise Http404("No active party package is currently available.")
        return package

    # This method finds or prepares the checkout state needed by the rest of the code.
    def get_checkout_state(self) -> dict[str, Any]:
        state = self.request.session.get(CHECKOUT_SESSION_KEY, {})
        return state if isinstance(state, dict) else {}

    # This method stores the current checkout step in the session so the user can continue to the next page.
    def save_checkout_state(self, state: dict[str, Any]) -> None:
        self.request.session[CHECKOUT_SESSION_KEY] = state
        self.request.session.modified = True

    # This method removes completed or cancelled checkout information from the session.
    def clear_checkout_state(self) -> None:
        self.request.session.pop(CHECKOUT_SESSION_KEY, None)
        self.request.session.modified = True

    # This method finds or prepares the selected tier needed by the rest of the code.
    def get_selected_tier(self) -> GuestPriceTier | None:
        tier_id = self.get_checkout_state().get("guest_tier_id")
        if not tier_id:
            return None
        return self.package.guest_price_tiers.filter(
            pk=tier_id,
            is_active=True,
        ).first()

    # This method finds or prepares the selected addons needed by the rest of the code.
    def get_selected_addons(self) -> list[AddonExperience]:
        addon_ids = self.get_checkout_state().get("addon_ids", [])
        if not isinstance(addon_ids, list):
            return []
        return list(
            AddonExperience.objects.filter(pk__in=addon_ids, is_active=True).order_by(
                "display_order", "name"
            )
        )

    # This method finds or prepares the quote context needed by the rest of the code.
    def get_quote_context(self) -> dict[str, Any]:
        guest_tier = self.get_selected_tier()
        addons = self.get_selected_addons()
        if guest_tier is None:
            return {}
        return {
            "package": self.package,
            "guest_tier": guest_tier,
            "selected_addons": addons,
            "quote": calculate_party_quote(guest_tier, addons),
        }


class PartyOptionsView(CheckoutStateMixin, FormView):
    """Step one: choose a children-count bracket and optional experiences."""

    template_name = "party_builder/options.html"
    form_class = PackageOptionsForm

    # This method passes the extra information that the form needs when it is created.
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["package"] = self.package
        state = self.get_checkout_state()
        if self.request.method == "GET" and state:
            kwargs["initial"] = {
                "guest_tier": state.get("guest_tier_id"),
                "addons": state.get("addon_ids", []),
            }
        elif self.request.method == "GET":
            default_tier = (
                self.package.guest_price_tiers.filter(
                    is_active=True,
                    is_default=True,
                ).first()
                or self.package.guest_price_tiers.filter(is_active=True).first()
            )
            if default_tier:
                kwargs["initial"] = {"guest_tier": default_tier.pk}
        return kwargs

    # This method adds the information that the template needs to display the page.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        selected_tier_id = str(form["guest_tier"].value() or "")
        selected_addon_ids = {str(value) for value in (form["addons"].value() or [])}
        tiers = list(form.fields["guest_tier"].queryset)
        addons = list(form.fields["addons"].queryset)
        selected_tier = next(
            (tier for tier in tiers if str(tier.pk) == selected_tier_id),
            tiers[0] if tiers and not form.is_bound else None,
        )
        selected_addons = [
            addon for addon in addons if str(addon.pk) in selected_addon_ids
        ]
        context.update(
            {
                "package": self.package,
                "price_tiers": tiers,
                "addon_options": [
                    {
                        "addon": addon,
                        "selected": str(addon.pk) in selected_addon_ids,
                    }
                    for addon in addons
                ],
                "selected_tier_id": selected_tier_id,
                "initial_quote": (
                    calculate_party_quote(selected_tier, selected_addons)
                    if selected_tier
                    else None
                ),
                "current_step": 1,
            }
        )
        return context

    # This method handles a correctly completed form and performs the requested action.
    def form_valid(self, form):
        guest_tier = form.cleaned_data["guest_tier"]
        addons = list(form.cleaned_data["addons"])
        state = self.get_checkout_state()
        state.update(
            {
                "package_id": self.package.pk,
                "guest_tier_id": guest_tier.pk,
                "addon_ids": [addon.pk for addon in addons],
            }
        )
        # Existing details remain available when users return to edit the cart.
        # The details form revalidates the exact guest count against the new bracket.
        self.save_checkout_state(state)
        return redirect("party_builder:party_builder_customer_details")


class PartyDetailsView(CheckoutStateMixin, FormView):
    """Step two: collect personal, venue, and event information."""

    template_name = "party_builder/details.html"
    form_class = PartyDetailsForm

    # This method performs setup and permission checks before the request reaches the page action.
    def dispatch(self, request, *args, **kwargs):
        self.package = self.get_package()
        if self.get_selected_tier() is None:
            return redirect("party_builder:party_builder_package_options")
        return FormView.dispatch(self, request, *args, **kwargs)

    # This method passes the extra information that the form needs when it is created.
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        guest_tier = self.get_selected_tier()
        kwargs["guest_tier"] = guest_tier
        kwargs["show_save_profile"] = self.request.user.is_authenticated
        kwargs["user"] = self.request.user
        state = self.get_checkout_state()
        if self.request.method == "GET" and state.get("details"):
            kwargs["initial"] = state["details"]
        elif self.request.method == "GET" and self.request.user.is_authenticated:
            from accounts.models import CustomerProfile
            profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
            kwargs["initial"] = {
                "contact_name": self.request.user.get_full_name(),
                "contact_email": self.request.user.email,
                "contact_phone": profile.phone,
                "event_address": profile.default_address,
                "postal_code": profile.default_postal_code,
            }
        return kwargs

    # This method adds the information that the template needs to display the page.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_quote_context())
        context["current_step"] = 2
        return context

    # This method handles a correctly completed form and performs the requested action.
    def form_valid(self, form):
        cleaned = form.cleaned_data
        state = self.get_checkout_state()
        state["details"] = {
            "contact_name": cleaned["contact_name"],
            "contact_email": cleaned["contact_email"],
            "contact_phone": cleaned["contact_phone"],
            "event_date": cleaned["event_date"].isoformat(),
            "event_time": (
                cleaned["event_time"].isoformat() if cleaned.get("event_time") else ""
            ),
            "guest_count": cleaned["guest_count"],
            "event_address": cleaned["event_address"],
            "postal_code": cleaned["postal_code"],
            "notes": cleaned.get("notes", ""),
        }
        self.save_checkout_state(state)
        if self.request.user.is_authenticated and cleaned.get("save_profile"):
            from accounts.models import CustomerProfile
            profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
            profile.phone = cleaned["contact_phone"]
            profile.default_address = cleaned["event_address"]
            profile.default_postal_code = cleaned["postal_code"]
            profile.save(
                update_fields=[
                    "phone",
                    "default_address",
                    "default_postal_code",
                    "updated_at",
                ]
            )
            self.request.user.first_name = cleaned["contact_name"].split(" ", 1)[0]
            if " " in cleaned["contact_name"]:
                self.request.user.last_name = cleaned["contact_name"].split(" ", 1)[1]
            self.request.user.email = cleaned["contact_email"]
            self.request.user.save(update_fields=["first_name", "last_name", "email"])
        return redirect("party_builder:party_builder_simulated_checkout")


class PartyCheckoutView(CheckoutStateMixin, FormView):
    """Step three: review the cart and validate a simulated card payment."""

    template_name = "party_builder/checkout.html"
    form_class = SimulatedPaymentForm

    # This method performs setup and permission checks before the request reaches the page action.
    def dispatch(self, request, *args, **kwargs):
        self.package = self.get_package()
        state = self.get_checkout_state()
        if self.get_selected_tier() is None:
            return redirect("party_builder:party_builder_package_options")
        if not state.get("details"):
            return redirect("party_builder:party_builder_customer_details")
        return FormView.dispatch(self, request, *args, **kwargs)

    # This method adds the information that the template needs to display the page.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_quote_context())
        context["details"] = self.get_checkout_state()["details"]
        context["current_step"] = 3
        return context

    # This method converts session text values back into the date and time objects used by Django.
    @staticmethod
    def _deserialize_details(raw_details: dict[str, Any]) -> dict[str, Any]:
        return {
            **raw_details,
            "event_date": date.fromisoformat(raw_details["event_date"]),
            "event_time": (
                time.fromisoformat(raw_details["event_time"])
                if raw_details.get("event_time")
                else None
            ),
        }

    # This method handles a correctly completed form and performs the requested action.
    def form_valid(self, form):
        state = self.get_checkout_state()
        guest_tier = self.get_selected_tier()
        addons = self.get_selected_addons()
        if guest_tier is None:
            return redirect("party_builder:party_builder_package_options")

        party_build = create_completed_party_build(
            package=self.package,
            guest_tier=guest_tier,
            addons=addons,
            details=self._deserialize_details(state["details"]),
            payment=form.safe_payment_result(),
            customer=self.request.user,
        )

        permitted_builds = self.request.session.get(
            AUTHORIZED_BUILD_SESSION_KEY,
            [],
        )
        permitted_builds.append(str(party_build.public_id))
        self.request.session[AUTHORIZED_BUILD_SESSION_KEY] = permitted_builds[-10:]
        self.clear_checkout_state()
        return HttpResponseRedirect(party_build.get_absolute_url())


class PartyBuilderRestartView(CheckoutStateMixin, View):
    """Clear the in-progress cart and return to the first checkout step."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        self.clear_checkout_state()
        return redirect("party_builder:party_builder_package_options")


class PartyBuildSuccessView(DetailView):
    """Show the completed simulated order only to its creating browser session."""

    model = PartyBuild
    template_name = "party_builder/build_success.html"
    context_object_name = "party_build"
    slug_field = "public_id"
    slug_url_kwarg = "public_id"

    # This method limits the database records to the ones the current user is allowed to see.
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("package", "guest_tier")
            .prefetch_related("addon_items__addon")
        )

    # This method finds or prepares the object needed by the rest of the code.
    def get_object(self, queryset=None):
        party_build = super().get_object(queryset)
        permitted_builds = self.request.session.get(
            AUTHORIZED_BUILD_SESSION_KEY,
            [],
        )
        owns_booking = (
            self.request.user.is_authenticated
            and party_build.customer_id == self.request.user.pk
        )
        if (
            str(party_build.public_id) not in permitted_builds
            and not owns_booking
            and not self.request.user.is_superuser
        ):
            raise Http404("This order summary is not available to this account or session.")
        return party_build
