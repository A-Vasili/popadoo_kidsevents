
from django.urls import path

from . import views

app_name = "party_builder"

# These URL patterns connect web addresses to the views that handle them.
urlpatterns = [
    path(
        "",
        views.PartyOptionsView.as_view(),
        name="party_builder_package_options",
    ),
    path(
        "details/",
        views.PartyDetailsView.as_view(),
        name="party_builder_customer_details",
    ),
    path(
        "checkout/",
        views.PartyCheckoutView.as_view(),
        name="party_builder_simulated_checkout",
    ),
    path(
        "restart/",
        views.PartyBuilderRestartView.as_view(),
        name="party_builder_restart_checkout",
    ),
    path(
        "complete/<uuid:public_id>/",
        views.PartyBuildSuccessView.as_view(),
        name="party_builder_order_success",
    ),
]
