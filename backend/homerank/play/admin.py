from typing import TYPE_CHECKING

from django.contrib import admin
from django.http import HttpRequest

from homerank.play.models import BotGame

# Django's ModelAdmin is generic for mypy, but can't be subscripted at runtime.
if TYPE_CHECKING:
    BotGameModelAdmin = admin.ModelAdmin[BotGame]
else:
    BotGameModelAdmin = admin.ModelAdmin


@admin.register(BotGame)
class BotGameAdmin(BotGameModelAdmin):
    """Games against bots, for operators to look into. Users play them in the app."""

    list_display = ("user", "opponent", "opponent_elo", "user_color", "status", "created_at")
    list_filter = ("opponent", "status")
    search_fields = ("user__username",)
    readonly_fields = tuple(field.name for field in BotGame._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
