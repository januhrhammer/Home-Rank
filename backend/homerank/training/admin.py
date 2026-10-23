from typing import TYPE_CHECKING

from django.contrib import admin
from django.http import HttpRequest

from homerank.training.models import Puzzle

# Django's ModelAdmin is generic for mypy, but can't be subscripted at runtime.
if TYPE_CHECKING:
    PuzzleModelAdmin = admin.ModelAdmin[Puzzle]
else:
    PuzzleModelAdmin = admin.ModelAdmin


@admin.register(Puzzle)
class PuzzleAdmin(PuzzleModelAdmin):
    """Puzzles, for operators to see what the extraction finds. Users get them automatically."""

    list_display = ("game", "ply", "user", "kind", "themes", "created_at")
    list_filter = ("kind",)
    search_fields = ("user__username",)
    readonly_fields = tuple(field.name for field in Puzzle._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
