
from django.urls import path

from . import views

app_name = "party_builder"

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
        "reviews/code/",
        views.PartyReviewCodeView.as_view(),
        name="party_builder_review_code",
    ),
    path(
        "reviews/<uuid:public_id>/",
        views.PartyReviewView.as_view(),
        name="party_builder_review",
    ),
    path(
        "reviews/<uuid:public_id>/submit/",
        views.PartyReviewSubmitView.as_view(),
        name="party_builder_review_submit",
    ),
    path(
        "recommendations/",
        views.PartyRecommendationView.as_view(),
        name="party_builder_recommendations",
    ),
    path(
        "complete/<uuid:public_id>/",
        views.PartyBuildSuccessView.as_view(),
        name="party_builder_order_success",
    ),
]
