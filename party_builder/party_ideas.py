"""Public discovery pages that feed choices into the existing party builder.

The management panel remains the source of catalogue data. These views expose
only active records, calculate public rating summaries, and keep every cart
change behind a CSRF-protected POST request.
"""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Avg, Count, DecimalField, F, Min, Prefetch, Q
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView

from .analytics import recommend_addons
from .forms import PartyIdeasFilterForm
from .models import AddonExperience, Category, GuestPriceTier, PartyBuild, PartyPackage
from .services import add_addon_to_session, checkout_state, resolve_active_package, select_package


VISIBLE_CATEGORY_FILTER = Q(parent__isnull=True) | Q(parent__is_active=True)


def visible_categories():
    """Return categories customers may browse, including safe parent details."""

    return (
        Category.objects.filter(is_active=True)
        .filter(VISIBLE_CATEGORY_FILTER)
        .select_related("parent")
        .order_by("display_order", "name")
    )


def public_package_queryset():
    """Return active packages with one query-friendly public rating summary."""

    completed_reviews = Q(
        builds__status=PartyBuild.Status.COMPLETED,
        builds__review__isnull=False,
        builds__customer_id=F("builds__review__reviewer_id"),
    )
    return (
        PartyPackage.objects.filter(is_active=True, category__is_active=True)
        .filter(Q(category__parent__isnull=True) | Q(category__parent__is_active=True))
        .select_related("category", "category__parent")
        .annotate(
            catalogue_price=Coalesce(
                Min(
                    "guest_price_tiers__total_price",
                    filter=Q(guest_price_tiers__is_active=True),
                ),
                F("base_price"),
                output_field=DecimalField(max_digits=8, decimal_places=2),
            ),
            rating_count=Count(
                "builds__review", filter=completed_reviews, distinct=True
            ),
            average_rating=Avg(
                "builds__review__package_score", filter=completed_reviews
            ),
        )
    )


def public_addon_queryset():
    """Return active experiences with verified completed-party rating totals."""

    completed_ratings = Q(
        build_items__build__status=PartyBuild.Status.COMPLETED,
        build_items__build_id=F("build_items__ratings__review__booking_id"),
        build_items__ratings__review__booking__status=PartyBuild.Status.COMPLETED,
        build_items__ratings__review__reviewer_id=F(
            "build_items__ratings__review__booking__customer_id"
        ),
    )
    return (
        AddonExperience.objects.filter(is_active=True, category__is_active=True)
        .filter(Q(category__parent__isnull=True) | Q(category__parent__is_active=True))
        .select_related("category", "category__parent")
        .annotate(
            catalogue_price=F("price"),
            rating_count=Count(
                "build_items__ratings", filter=completed_ratings, distinct=True
            ),
            average_rating=Avg(
                "build_items__ratings__score", filter=completed_ratings
            ),
        )
    )


def _duration_filter(value: str) -> Q:
    if value == "short":
        return Q(duration_minutes__lte=30)
    if value == "medium":
        return Q(duration_minutes__gt=30, duration_minutes__lte=60)
    if value == "long":
        return Q(duration_minutes__gt=60)
    return Q()


def _category_ids(category: Category | None) -> list[int]:
    if category is None:
        return []
    if category.parent_id:
        return [category.pk]
    return [
        category.pk,
        *category.children.filter(is_active=True).values_list("pk", flat=True),
    ]


def _normalise_card(item, kind: str) -> dict:
    """Give package and experience templates one small, shared card shape."""

    return {
        "kind": kind,
        "object": item,
        "name": item.name,
        "description": item.short_description,
        "price": item.catalogue_price,
        "duration_minutes": item.duration_minutes,
        "category": item.category,
        "average_rating": item.average_rating,
        "rating_count": item.rating_count,
        "display_order": item.display_order,
        "is_featured": kind == "experience" and item.is_featured,
    }


def _sort_cards(cards: list[dict], ordering: str) -> None:
    if ordering == "name":
        key = lambda card: (card["name"].casefold(), card["kind"])
    elif ordering == "price_asc":
        key = lambda card: (card["price"], card["name"].casefold())
    elif ordering == "price_desc":
        key = lambda card: (-card["price"], card["name"].casefold())
    elif ordering == "rating":
        key = lambda card: (
            -float(card["average_rating"] or 0),
            -card["rating_count"],
            card["name"].casefold(),
        )
    elif ordering == "reviews":
        key = lambda card: (
            -card["rating_count"],
            -float(card["average_rating"] or 0),
            card["name"].casefold(),
        )
    else:
        key = lambda card: (
            0 if card["kind"] == "package" else 1,
            card["display_order"],
            card["name"].casefold(),
        )
    cards.sort(key=key)


def _query_string(querydict, **changes) -> str:
    values = querydict.copy()
    values.pop("page", None)
    for key, value in changes.items():
        if value in (None, ""):
            values.pop(key, None)
        else:
            values[key] = value
    return urlencode(values, doseq=True)


class PartyIdeasListView(TemplateView):
    """Search, filter and paginate public packages and experiences together."""

    template_name = "party_builder/party_ideas/list.html"
    forced_category: Category | None = None

    def get_forced_category(self):
        return self.forced_category

    def _validated_filters(self):
        data = self.request.GET.copy()
        category = self.get_forced_category()
        if category:
            data["category"] = category.slug
        form = PartyIdeasFilterForm(data or None)
        if form.is_valid():
            return form, form.cleaned_data
        # Invalid URL values stay visible with field errors but cannot reach ORM
        # ordering or numeric comparisons.
        return form, {
            "q": "",
            "type": "all",
            "min_price": None,
            "max_price": None,
            "category": category,
            "duration": "",
            "min_rating": "",
            "featured": False,
            "sort": "recommended",
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form, filters = self._validated_filters()
        packages = public_package_queryset()
        addons = public_addon_queryset()

        search = filters.get("q") or ""
        if search:
            packages = packages.filter(
                Q(name__icontains=search)
                | Q(short_description__icontains=search)
                | Q(included_experiences__icontains=search)
                | Q(slug__icontains=search)
                | Q(category__name__icontains=search)
                | Q(category__parent__name__icontains=search)
            )
            addons = addons.filter(
                Q(name__icontains=search)
                | Q(short_description__icontains=search)
                | Q(slug__icontains=search)
                | Q(category__name__icontains=search)
                | Q(category__parent__name__icontains=search)
            )

        category = filters.get("category")
        category_ids = _category_ids(category)
        if category_ids:
            packages = packages.filter(category_id__in=category_ids)
            addons = addons.filter(category_id__in=category_ids)

        duration_query = _duration_filter(filters.get("duration") or "")
        packages = packages.filter(duration_query)
        addons = addons.filter(duration_query)

        minimum = filters.get("min_price")
        maximum = filters.get("max_price")
        if minimum is not None:
            packages = packages.filter(catalogue_price__gte=minimum)
            addons = addons.filter(catalogue_price__gte=minimum)
        if maximum is not None:
            packages = packages.filter(catalogue_price__lte=maximum)
            addons = addons.filter(catalogue_price__lte=maximum)

        minimum_rating = filters.get("min_rating")
        if minimum_rating:
            threshold = Decimal(minimum_rating)
            packages = packages.filter(average_rating__gte=threshold)
            addons = addons.filter(average_rating__gte=threshold)

        idea_type = filters.get("type") or "all"
        include_packages = idea_type in {"all", "package"}
        include_addons = idea_type in {"all", "experience"}
        if filters.get("featured"):
            include_packages = False
            addons = addons.filter(is_featured=True)

        cards: list[dict] = []
        if include_packages:
            cards.extend(_normalise_card(item, "package") for item in packages.distinct())
        if include_addons:
            cards.extend(_normalise_card(item, "experience") for item in addons.distinct())
        _sort_cards(cards, filters.get("sort") or "recommended")

        paginator = Paginator(cards, 12)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        base_query = _query_string(self.request.GET)

        main_categories = list(
            visible_categories()
            .filter(parent__isnull=True)
            .prefetch_related(
                Prefetch(
                    "children",
                    queryset=Category.objects.filter(is_active=True).order_by(
                        "display_order", "name"
                    ),
                    to_attr="active_children",
                )
            )
        )
        active_filters = []
        labels = {
            "q": "Search",
            "min_price": "Minimum price",
            "max_price": "Maximum price",
            "duration": "Duration",
            "min_rating": "Rating",
            "featured": "Featured",
        }
        for key, label in labels.items():
            value = filters.get(key)
            if value:
                active_filters.append(
                    {
                        "label": f"{label}: {value if value is not True else 'yes'}",
                        "remove_query": _query_string(self.request.GET, **{key: None}),
                    }
                )
        if category and not self.get_forced_category():
            active_filters.append(
                {
                    "label": f"Category: {category}",
                    "remove_query": _query_string(self.request.GET, category=None),
                }
            )

        current_category = self.get_forced_category()
        current_category_children = (
            list(
                current_category.children.filter(is_active=True).order_by(
                    "display_order", "name"
                )
            )
            if current_category and current_category.parent_id is None
            else []
        )

        context.update(
            {
                "filter_form": form,
                "filters": filters,
                "page_obj": page_obj,
                "paginator": paginator,
                "result_count": paginator.count,
                "base_query": base_query,
                "main_categories": main_categories,
                "active_filters": active_filters,
                "current_category": current_category,
                "current_category_children": current_category_children,
                "type_tabs": [
                    {
                        "value": value,
                        "label": label,
                        "translation_key": {
                            "all": "partyIdeas.all",
                            "package": "partyIdeas.startingPackages",
                            "experience": "partyIdeas.experiences",
                        }[value],
                        "active": idea_type == value,
                        "query": _query_string(self.request.GET, type=value),
                    }
                    for value, label in PartyIdeasFilterForm.TYPE_CHOICES
                ],
            }
        )
        return context


class PartyIdeasCategoryView(PartyIdeasListView):
    """Reuse the catalogue results while fixing the scope to one category."""

    def dispatch(self, request, *args, **kwargs):
        self.forced_category = get_object_or_404(
            visible_categories(), slug=kwargs["slug"]
        )
        return super().dispatch(request, *args, **kwargs)


class PartyPackageDetailView(DetailView):
    """Present an active package as a flexible starting point."""

    template_name = "party_builder/party_ideas/package_detail.html"
    context_object_name = "package"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return public_package_queryset().prefetch_related(
            Prefetch(
                "guest_price_tiers",
                queryset=GuestPriceTier.objects.filter(is_active=True).order_by(
                    "display_order", "min_guests"
                ),
                to_attr="active_tiers",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recommendations"] = recommend_addons(
            selected_ids=[], package=self.object
        )
        return context


class PartyAddonDetailView(DetailView):
    """Show one active experience and related ideas without private feedback."""

    template_name = "party_builder/party_ideas/addon_detail.html"
    context_object_name = "addon"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return public_addon_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        package = resolve_active_package(self.request.session)
        if package is None:
            recommendations = []
        else:
            recommendations = recommend_addons(
                selected_ids=[self.object.pk], package=package
            )
        context.update({"recommendations": recommendations, "current_package": package})
        return context


class StartPackageView(View):
    """Put an active package into the builder through a protected POST action."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        package = get_object_or_404(
            public_package_queryset(), slug=kwargs["slug"]
        )
        select_package(request.session, package)
        messages.success(
            request,
            f"{package.name} is now your starting package. Choose the group size next.",
        )
        return redirect("party_builder:party_builder_package_options")


class AddAddonView(View):
    """Add an active experience to the same session cart used at checkout."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        addon = get_object_or_404(
            public_addon_queryset(), slug=kwargs["slug"]
        )
        add_addon_to_session(request.session, addon)
        messages.success(request, f"{addon.name} was added to your party choices.")
        builder_url = reverse("party_builder:party_builder_package_options")
        return redirect(f"{builder_url}#addon-{addon.pk}")
