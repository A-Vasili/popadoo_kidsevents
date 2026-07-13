"""Customer-facing routes for browsing ideas before using the builder."""

from django.urls import path

from . import party_ideas

app_name = "party_ideas"

urlpatterns = [
    path("", party_ideas.PartyIdeasListView.as_view(), name="list"),
    path(
        "packages/<slug:slug>/",
        party_ideas.PartyPackageDetailView.as_view(),
        name="package_detail",
    ),
    path(
        "experiences/<slug:slug>/",
        party_ideas.PartyAddonDetailView.as_view(),
        name="addon_detail",
    ),
    path(
        "categories/<slug:slug>/",
        party_ideas.PartyIdeasCategoryView.as_view(),
        name="category_detail",
    ),
    path(
        "packages/<slug:slug>/start/",
        party_ideas.StartPackageView.as_view(),
        name="start_package",
    ),
    path(
        "experiences/<slug:slug>/add/",
        party_ideas.AddAddonView.as_view(),
        name="add_addon",
    ),
]
