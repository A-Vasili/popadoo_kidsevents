"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
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
