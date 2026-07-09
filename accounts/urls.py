# This file gives clear names and paths to all account-related pages.
# Comments in this file explain the purpose of each section without changing how the program works.

from django.urls import path

from . import views

app_name = "accounts"

# These URL patterns connect web addresses to the views that handle them.
urlpatterns = [
    path("sign-up/", views.SignUpView.as_view(), name="accounts_sign_up"),
    path("sign-in/", views.SignInView.as_view(), name="accounts_sign_in"),
    path("sign-out/", views.SignOutView.as_view(), name="accounts_sign_out"),
    path("profile/", views.ProfileUpdateView.as_view(), name="accounts_profile"),
    path(
        "dashboard/",
        views.CustomerDashboardView.as_view(),
        name="accounts_customer_dashboard",
    ),
]
