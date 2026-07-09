from __future__ import annotations

from decimal import Decimal

from django.http import Http404, HttpResponseRedirect
from django.views.generic import CreateView, DetailView

from .forms import PartyBuildForm
from .models import AddonExperience, PartyBuild, PartyPackage
from .services import calculate_party_quote


class PartyBuilderCreateView(CreateView):
    """Render and process the accessible create-your-own-party workflow."""

    model = PartyBuild
    form_class = PartyBuildForm
    template_name = "party_builder/builder.html"

    package: PartyPackage

    def dispatch(self, request, *args, **kwargs):
        self.package = self._get_package()
        return super().dispatch(request, *args, **kwargs)

    def _get_package(self) -> PartyPackage:
        packages = PartyPackage.objects.filter(is_active=True)
        package_slug = self.kwargs.get("package_slug")

        if package_slug:
            try:
                return packages.get(slug=package_slug)
            except PartyPackage.DoesNotExist as error:
                raise Http404("The requested party package is unavailable.") from error

        package = packages.filter(is_default=True).first() or packages.first()
        if package is None:
            raise Http404("No active party package is currently available.")

        return package

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["package"] = self.package
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        addons = list(
            AddonExperience.objects.filter(is_active=True).order_by(
                "display_order", "name"
            )
        )

        selected_values = set(self.request.POST.getlist("addons"))
        selected_addons = [
            addon for addon in addons if str(addon.pk) in selected_values
        ]
        quote = calculate_party_quote(self.package, selected_addons)

        context.update(
            {
                "package": self.package,
                "addon_options": [
                    {
                        "addon": addon,
                        "selected": str(addon.pk) in selected_values,
                    }
                    for addon in addons
                ],
                "initial_quote": quote,
            }
        )
        return context

    def form_valid(self, form):
        self.object = form.save()

        # The success page contains personal details, so authorize it in-session.
        permitted_builds = self.request.session.get("party_builder_builds", [])
        permitted_builds.append(str(self.object.public_id))
        self.request.session["party_builder_builds"] = permitted_builds[-10:]

        return HttpResponseRedirect(self.get_success_url())


class PartyBuildSuccessView(DetailView):
    """Show the submitted summary only to the browser session that created it."""

    model = PartyBuild
    template_name = "party_builder/build_success.html"
    context_object_name = "party_build"
    slug_field = "public_id"
    slug_url_kwarg = "public_id"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("package")
            .prefetch_related("addon_items__addon")
        )

    def get_object(self, queryset=None):
        party_build = super().get_object(queryset)
        permitted_builds = self.request.session.get("party_builder_builds", [])

        if str(party_build.public_id) not in permitted_builds:
            raise Http404("This party summary is not available in this session.")

        return party_build

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        addon_total = sum(
            (item.unit_price for item in self.object.addon_items.all()),
            Decimal("0.00"),
        )
        context["addon_total"] = addon_total
        return context
