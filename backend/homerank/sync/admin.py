from typing import TYPE_CHECKING

from django.contrib import admin
from django.http import HttpRequest

from homerank.sync.models import LinkedAccount, SyncRun

# Django's ModelAdmin is generic for mypy, but can't be subscripted at runtime.
if TYPE_CHECKING:
    LinkedAccountModelAdmin = admin.ModelAdmin[LinkedAccount]
    SyncRunModelAdmin = admin.ModelAdmin[SyncRun]
else:
    LinkedAccountModelAdmin = SyncRunModelAdmin = admin.ModelAdmin


@admin.register(LinkedAccount)
class LinkedAccountAdmin(LinkedAccountModelAdmin):
    """Linked accounts, for operators to see what gets synced. Users link them in the app."""

    list_display = ("username", "platform", "user", "enabled", "synced_until")
    list_filter = ("platform", "enabled")
    search_fields = ("username", "user__username")
    readonly_fields = ("user", "platform", "username", "synced_until", "created_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


@admin.register(SyncRun)
class SyncRunAdmin(SyncRunModelAdmin):
    """Syncs, for operators to see what is running or failed."""

    list_display = ("account", "status", "games_imported", "games_failed", "created_at")
    list_filter = ("status", "account__platform")
    search_fields = ("account__username", "account__user__username")
    readonly_fields = tuple(field.name for field in SyncRun._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
