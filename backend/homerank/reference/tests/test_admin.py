"""The admin pages for reference databases and their imports."""

from http import HTTPStatus
from pathlib import Path

import pytest
import zstandard
from django.db import connection
from django.test import Client
from django.urls import reverse
from procrastinate.contrib.django.models import ProcrastinateJob
from pytest_django import Settings

from homerank.reference.models import ReferenceDatabase, ReferenceImport, ReferenceImportFile

pytestmark = pytest.mark.django_db


def partitions(database_id: int) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE tablename LIKE %s", [f"%\\_{database_id}"]
        )
        return {name for (name,) in cursor.fetchall()}


def test_creating_a_database_creates_its_partitions(admin_client: Client) -> None:
    response = admin_client.post(
        reverse("admin:reference_referencedatabase_add"),
        {"name": "Masters", "description": "", "depth": 20},
    )

    assert response.status_code == HTTPStatus.FOUND
    database = ReferenceDatabase.objects.get()
    assert database.depth == 20  # noqa: PLR2004
    assert f"reference_game_{database.pk}" in partitions(database.pk)


def test_deleting_a_database_drops_its_partitions(admin_client: Client) -> None:
    admin_client.post(
        reverse("admin:reference_referencedatabase_add"), {"name": "Masters", "depth": 30}
    )
    database = ReferenceDatabase.objects.get()

    admin_client.post(
        reverse("admin:reference_referencedatabase_delete", args=[database.pk]), {"post": "yes"}
    )

    assert not ReferenceDatabase.objects.exists()
    assert partitions(database.pk) == set()


def test_files_in_the_import_folder_can_be_imported(
    admin_client: Client, settings: Settings, tmp_path: Path
) -> None:
    settings.REFERENCE_IMPORT_DIR = tmp_path
    (tmp_path / "masters.pgn.zst").write_bytes(
        zstandard.ZstdCompressor().compress(b'[White "A"]\n\n1. e4 *\n')
    )
    admin_client.post(
        reverse("admin:reference_referencedatabase_add"), {"name": "Masters", "depth": 30}
    )
    url = reverse(
        "admin:reference_referencedatabase_import", args=[ReferenceDatabase.objects.get().pk]
    )

    page = admin_client.get(url)
    response = admin_client.post(url, {"chosen": ["masters.pgn.zst"]})

    assert "masters.pgn.zst" in page.content.decode()
    assert response.status_code == HTTPStatus.FOUND
    reference_import = ReferenceImport.objects.get()
    assert [f.path for f in reference_import.files.all()] == [str(tmp_path / "masters.pgn.zst")]
    assert ProcrastinateJob.objects.filter(id=reference_import.job_id, queue_name="bulk").exists()


def test_imports_show_their_progress(admin_client: Client) -> None:
    database = ReferenceDatabase.objects.create(name="Masters")
    reference_import = ReferenceImport.objects.create(database=database, status="reading")
    ReferenceImportFile.objects.create(
        reference_import=reference_import,
        path="/data/import/a.7z",
        size=10,
        progress=0.42,
        games_read=1234,
    )

    changelist = admin_client.get(
        reverse("admin:reference_referenceimport_changelist")
    ).content.decode()
    detail = admin_client.get(
        reverse("admin:reference_referenceimport_change", args=[reference_import.pk])
    ).content.decode()

    assert "42% · 1,234 games" in changelist
    assert "/data/import/a.7z" in detail
