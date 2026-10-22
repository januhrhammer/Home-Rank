from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from pytest_django import Settings

from homerank.accounts.models import User
from homerank.games.models import ImportRun

IMPORTS = "/api/v1/games/imports"
GAME = b"""\
[White "Anna"]
[Black "Ben"]
[Result "1-0"]

1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0
"""

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def data_dir(settings: Settings, tmp_path: Path) -> Path:
    settings.DATA_DIR = tmp_path
    return tmp_path


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


@pytest.fixture
def alice_client(client: Client, alice: User) -> Client:
    client.force_login(alice)
    return client


def upload(client: Client, name: str = "club.pgn", content: bytes = GAME) -> Any:
    return client.post(IMPORTS, {"file": SimpleUploadedFile(name, content)})


def make_run(user: User, file_name: str = "club.pgn") -> ImportRun:
    return ImportRun.objects.create(user=user, file_name=file_name, file_size=len(GAME))


def test_upload_starts_an_import(alice_client: Client, alice: User) -> None:
    response = upload(alice_client)

    assert response.status_code == HTTPStatus.ACCEPTED
    body = response.json()
    run = ImportRun.objects.get(user=alice)
    assert body["id"] == run.pk
    assert body["file_name"] == "club.pgn"
    assert body["status"] == "queued"
    assert (body["file_size"], body["bytes_read"]) == (len(GAME), 0)
    assert body["errors"] == []


def test_upload_requires_login(client: Client) -> None:
    response = upload(client)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert not ImportRun.objects.exists()


def test_upload_requires_the_csrf_token(alice: User) -> None:
    client = Client(enforce_csrf_checks=True)
    client.force_login(alice)

    response = upload(client)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert not ImportRun.objects.exists()


def test_only_pgn_files_can_be_imported(alice_client: Client) -> None:
    response = upload(alice_client, name="games.zip")

    assert response.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    assert response.json()["detail"] == "Only PGN files (.pgn) can be imported."
    assert not ImportRun.objects.exists()


def test_the_extension_may_be_upper_case(alice_client: Client) -> None:
    assert upload(alice_client, name="CLUB.PGN").status_code == HTTPStatus.ACCEPTED


def test_files_over_the_limit_are_refused(alice_client: Client, settings: Settings) -> None:
    settings.IMPORT_MAX_BYTES = 2 * 1024 * 1024

    response = upload(alice_client, content=GAME * 30_000)  # about 3 MB

    assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert response.json()["detail"] == "PGN files can be at most 2 MB."
    assert not ImportRun.objects.exists()


def test_lists_imports_newest_first(alice_client: Client, alice: User) -> None:
    for name in ("first.pgn", "second.pgn", "third.pgn"):
        make_run(alice, name)

    response = alice_client.get(IMPORTS, {"limit": 2})

    assert response.status_code == HTTPStatus.OK
    page = response.json()
    assert [run["file_name"] for run in page["items"]] == ["third.pgn", "second.pgn"]
    assert page["total"] == len(["first.pgn", "second.pgn", "third.pgn"])
    rest = alice_client.get(IMPORTS, {"limit": 2, "offset": 2}).json()
    assert [run["file_name"] for run in rest["items"]] == ["first.pgn"]


def test_pages_have_a_maximum_size(alice_client: Client) -> None:
    response = alice_client.get(IMPORTS, {"limit": 101})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_shows_an_imports_progress(alice_client: Client, alice: User) -> None:
    run = make_run(alice)
    ImportRun.objects.filter(pk=run.pk).update(
        status=ImportRun.Status.RUNNING,
        bytes_read=40,
        games_imported=1,
        games_failed=1,
        errors=[{"line": 9, "reason": "illegal san: 'Qxf8'"}],
    )

    body = alice_client.get(f"{IMPORTS}/{run.pk}").json()

    assert (body["status"], body["bytes_read"]) == ("running", 40)
    assert (body["games_imported"], body["games_failed"]) == (1, 1)
    assert body["errors"] == [{"line": 9, "reason": "illegal san: 'Qxf8'"}]


# Isolation: users only ever see their own imports.


def test_lists_only_your_own_imports(alice_client: Client, alice: User) -> None:
    make_run(alice, "mine.pgn")
    make_run(User.objects.create_user(username="bob"), "bobs.pgn")

    page = alice_client.get(IMPORTS).json()

    assert [run["file_name"] for run in page["items"]] == ["mine.pgn"]
    assert page["total"] == 1


def test_someone_elses_import_is_not_found(alice_client: Client) -> None:
    bobs = make_run(User.objects.create_user(username="bob"))

    response = alice_client.get(f"{IMPORTS}/{bobs.pk}")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response["Content-Type"] == "application/problem+json"


def test_an_unknown_import_is_not_found(alice_client: Client) -> None:
    assert alice_client.get(f"{IMPORTS}/999999").status_code == HTTPStatus.NOT_FOUND
