from typing import TYPE_CHECKING

from django.contrib import admin
from django.http import HttpRequest

from homerank.analysis.models import AnalysisRun, AnalysisSettings

# Django's ModelAdmin is generic for mypy, but can't be subscripted at runtime.
if TYPE_CHECKING:
    AnalysisRunModelAdmin = admin.ModelAdmin[AnalysisRun]
    AnalysisSettingsModelAdmin = admin.ModelAdmin[AnalysisSettings]
else:
    AnalysisRunModelAdmin = AnalysisSettingsModelAdmin = admin.ModelAdmin


@admin.register(AnalysisRun)
class AnalysisRunAdmin(AnalysisRunModelAdmin):
    """Analyses, for operators to see what waits, runs or failed. Users start them in the app."""

    list_display = ("game", "user", "status", "depth", "positions_done", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username",)
    readonly_fields = tuple(field.name for field in AnalysisRun._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


@admin.register(AnalysisSettings)
class AnalysisSettingsAdmin(AnalysisSettingsModelAdmin):
    list_display = ("user", "auto_analyse", "inaccuracy", "mistake", "blunder")
    search_fields = ("user__username",)
    readonly_fields = ("user",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
