# This file maps readable website addresses to the part of Popadoo responsible for answering each
# request.
# The route order also protects specialised management and messaging paths from being swallowed by
# broader URL groups.
# It contains no page logic; the matched view performs the actual work.
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

# These named routes connect stable website addresses to the views that handle each customer or
# staff request.
# Permission checks remain inside the views, so knowing an address never grants access by itself.
urlpatterns = [
    path("", include("core.urls")),
    # Exact chat routes are resolved before the broader account and management includes.
    path("", include("communications.urls")),
    path("accounts/", include("accounts.urls")),
    path("operations/", include("operations.urls")),
    path("management/", include(("operations.management_urls", "management"), namespace="management")),
    path("party-ideas/", include(("party_builder.party_ideas_urls", "party_ideas"), namespace="party_ideas")),
    path("party-builder/", include("party_builder.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
