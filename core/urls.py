from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="core_home"),
    path("gallery/", views.gallery, name="core_gallery"),
    path("about/", views.about, name="core_about"),
    path("testimonials/", views.testimonials, name="core_testimonials"),
    # Preserve old bookmarks while removing the obsolete standalone pages.
    path(
        "packages/",
        RedirectView.as_view(
            pattern_name="party_builder:party_builder_package_options",
            permanent=True,
        ),
        name="core_packages_redirect",
    ),
    path(
        "contact/",
        RedirectView.as_view(
            pattern_name="party_builder:party_builder_package_options",
            permanent=True,
        ),
        name="core_contact_redirect",
    ),
]
