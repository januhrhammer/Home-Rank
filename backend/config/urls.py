"""Root URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.urls import URLPattern, URLResolver, path

urlpatterns: list[URLPattern | URLResolver] = [
    path(settings.ADMIN_URL, admin.site.urls),
]
