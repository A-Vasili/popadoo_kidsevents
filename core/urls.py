"""Public information pages and compatibility redirects."""

from django.urls import path
from django.views.generic import RedirectView, TemplateView

from .views import TestimonialsView

app_name = "core"

urlpatterns = [
    path("", TemplateView.as_view(template_name="core/index.html"), name="core_home"),
    path("gallery/", TemplateView.as_view(template_name="core/gallery.html"), name="core_gallery"),
    path("about/", TemplateView.as_view(template_name="core/about.html"), name="core_about"),
    path("testimonials/", TestimonialsView.as_view(), name="core_testimonials"),
    path(
        "packages/",
        RedirectView.as_view(
            pattern_name="party_ideas:list",
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
