"""Root URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.urls import URLPattern, URLResolver, path, re_path

from config.api import api
from homerank.core.errors import api_not_found
from homerank.core.health import healthz, readyz

urlpatterns: list[URLPattern | URLResolver] = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", api.urls),
    # Must come after the API: catches every /api/ URL that matched no endpoint.
    re_path(r"^api/", api_not_found),
    path("healthz", healthz),
    path("readyz", readyz),
]
