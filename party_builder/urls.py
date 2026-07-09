from django.urls import path

from . import views

# Namespaced nicknames combine the app and view purpose, for example:
# party_builder:party_builder_builder
app_name = "party_builder"

urlpatterns = [
    path(
        "",
        views.PartyBuilderCreateView.as_view(),
        name="party_builder_builder",
    ),
    path(
        "package/<slug:package_slug>/",
        views.PartyBuilderCreateView.as_view(),
        name="party_builder_package",
    ),
    path(
        "complete/<uuid:public_id>/",
        views.PartyBuildSuccessView.as_view(),
        name="party_builder_success",
    ),
]
