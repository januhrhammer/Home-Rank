"""Root URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.urls import URLPattern, URLResolver, path

from config.api import api
from homerank.core.health import healthz, readyz

urlpatterns: list[URLPattern | URLResolver] = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", api.urls),
    path("healthz", healthz),
    path("readyz", readyz),
]
