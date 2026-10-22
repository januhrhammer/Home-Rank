from typing import TYPE_CHECKING

from django.contrib import admin
from django.http import HttpRequest

from homerank.games.models import ImportRun

# Django's ModelAdmin is generic for mypy, but can't be subscripted at runtime.
if TYPE_CHECKING:
    ImportRunModelAdmin = admin.ModelAdmin[ImportRun]
else:
    ImportRunModelAdmin = admin.ModelAdmin


@admin.register(ImportRun)
class ImportRunAdmin(ImportRunModelAdmin):
    """Imports, for operators to see what is running or failed. Users start them in the app."""

    list_display = ("file_name", "user", "status", "games_imported", "games_failed", "created_at")
    list_filter = ("status",)
    search_fields = ("file_name", "user__username")
    readonly_fields = tuple(field.name for field in ImportRun._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
