"""Admin pages for reference databases: create and delete them, import files, watch imports.

Users read reference databases in the app; only staff manage them, here or with
`manage.py import_reference`.
"""

from typing import TYPE_CHECKING, Any

from django import forms
from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html

from homerank.core.errors import DomainError
from homerank.reference import repository, services
from homerank.reference.models import ReferenceDatabase, ReferenceImport, ReferenceImportFile

# Django's ModelAdmin is generic for mypy, but can't be subscripted at runtime.
if TYPE_CHECKING:
    DatabaseModelAdmin = admin.ModelAdmin[ReferenceDatabase]
    ImportModelAdmin = admin.ModelAdmin[ReferenceImport]
    FileInline = admin.TabularInline[ReferenceImportFile, ReferenceImport]
else:
    DatabaseModelAdmin = ImportModelAdmin = admin.ModelAdmin
    FileInline = admin.TabularInline


@admin.register(ReferenceDatabase)
class ReferenceDatabaseAdmin(DatabaseModelAdmin):
    list_display = ("name", "status", "game_count", "depth", "imported_at", "import_link")
    readonly_fields = ("status", "game_count", "imported_at")
    fields = ("name", "description", "depth", "status", "game_count", "imported_at")

    def get_readonly_fields(
        self, request: HttpRequest, obj: ReferenceDatabase | None = None
    ) -> Any:
        # The depth applies to everything imported; it can't change afterwards.
        return (*self.readonly_fields, "depth", "import_link") if obj else self.readonly_fields

    def get_fields(self, request: HttpRequest, obj: ReferenceDatabase | None = None) -> Any:
        # A saved database's page links to its import page, as the list does.
        fields = super().get_fields(request, obj)
        return (*fields, "import_link") if obj else fields

    @admin.display(description="Import")
    def import_link(self, obj: ReferenceDatabase) -> str:
        url = reverse("admin:reference_referencedatabase_import", args=[obj.pk])
        return format_html('<a href="{}">Import files…</a>', url)

    def response_add(
        self, request: HttpRequest, obj: ReferenceDatabase, post_url_continue: str | None = None
    ) -> HttpResponse:
        # A new database is empty, so "Save" goes on to choosing files to import into it.
        if "_continue" in request.POST or "_addanother" in request.POST:
            return super().response_add(request, obj, post_url_continue)
        messages.success(request, f"{obj} was added. Choose the files to import into it.")
        return HttpResponseRedirect(
            reverse("admin:reference_referencedatabase_import", args=[obj.pk])
        )

    def save_model(
        self, request: HttpRequest, obj: ReferenceDatabase, form: Any, change: bool
    ) -> None:
        super().save_model(request, obj, form, change)
        if not change:
            repository.create_partitions(obj.pk)

    def delete_model(self, request: HttpRequest, obj: ReferenceDatabase) -> None:
        services.delete_database(obj)

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[ReferenceDatabase]) -> None:
        for database in queryset:
            services.delete_database(database)

    def get_urls(self) -> list[URLPattern]:
        view = self.admin_site.admin_view(self.import_view)
        return [
            path("<int:database_id>/import/", view, name="reference_referencedatabase_import"),
            *super().get_urls(),
        ]

    def import_view(self, request: HttpRequest, database_id: int) -> HttpResponse:
        """Choose files from REFERENCE_IMPORT_DIR and queue their import."""
        database = get_object_or_404(ReferenceDatabase, pk=database_id)
        files = services.importable_files()
        form = ImportForm(request.POST or None, names=[str(f) for f in files])
        if request.method == "POST" and form.is_valid():
            try:
                services.start_import(database=database, files=form.cleaned_data["chosen"])
            except DomainError as error:
                messages.error(request, str(error))
            else:
                messages.success(request, f"The import into {database} is queued.")
                return HttpResponseRedirect(reverse("admin:reference_referenceimport_changelist"))
        paths = [services.import_file_path(str(f)) for f in files]
        estimates = {
            str(f): services.estimate([p], database.depth)
            for f, p in zip(files, paths, strict=True)
        }
        context = {
            **self.admin_site.each_context(request),
            "title": f"Import files into {database}",
            "database": database,
            "form": form,
            "estimates": estimates,
            "folder": services.import_folder(),
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/reference/import.html", context)


class ImportForm(forms.Form):
    # Not "files": that is the form's own attribute for uploaded files.
    chosen = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args: Any, names: list[str], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["chosen"].choices = [(name, name) for name in names]  # type: ignore[attr-defined]


class ReferenceImportFileInline(FileInline):
    model = ReferenceImportFile
    extra = 0
    can_delete = False
    fields = ("path", "percent", "games_read", "games_failed", "done", "errors")
    readonly_fields = fields

    @admin.display(description="Read")
    def percent(self, obj: ReferenceImportFile) -> str:
        return f"{obj.progress:.0%}"

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(ReferenceImport)
class ReferenceImportAdmin(ImportModelAdmin):
    """Imports, with each file's progress. Reload the page to follow a running import."""

    list_display = ("database", "status", "progress", "created_at", "finished_at")
    list_filter = ("status",)
    readonly_fields = ("database", "status", "error", "created_at", "started_at", "finished_at")
    fields = readonly_fields
    inlines = (ReferenceImportFileInline,)

    @admin.display(description="Progress")
    def progress(self, obj: ReferenceImport) -> str:
        files = list(obj.files.all())
        games = sum(f.games_read for f in files)
        done = sum(f.progress for f in files) / max(1, len(files))
        return f"{done:.0%} · {games:,} games"

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
