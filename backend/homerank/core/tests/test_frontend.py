from http import HTTPStatus
from pathlib import Path

import pytest
from django.test import Client
from django.urls import reverse
from pytest_django import Settings

INDEX_HTML = b"<!doctype html><title>Home-Rank</title>"


@pytest.fixture
def built_frontend(settings: Settings, tmp_path: Path) -> None:
    """Stands in for frontend/dist after `pnpm build`."""
    (tmp_path / "index.html").write_bytes(INDEX_HTML)
    settings.FRONTEND_DIR = tmp_path


@pytest.mark.parametrize("address", ["/", "/login", "/games/42"])
@pytest.mark.usefixtures("built_frontend")
def test_frontend_addresses_get_index_html(client: Client, address: str) -> None:
    response = client.get(address)

    assert response.status_code == HTTPStatus.OK
    assert response.content == INDEX_HTML


@pytest.mark.usefixtures("built_frontend")
def test_index_html_is_never_cached(client: Client) -> None:
    assert "no-cache" in client.get("/")["Cache-Control"]


@pytest.mark.usefixtures("built_frontend")
def test_api_and_health_addresses_are_not_taken_over(client: Client) -> None:
    assert client.get("/api/v1/no-such-endpoint")["Content-Type"] == "application/problem+json"
    assert client.get("/healthz").json() == {"status": "ok"}


@pytest.mark.usefixtures("built_frontend")
def test_admin_address_without_its_slash_still_redirects(client: Client) -> None:
    admin = reverse("admin:index")

    response = client.get(admin.rstrip("/"))

    assert response.status_code == HTTPStatus.MOVED_PERMANENTLY
    assert response["Location"] == admin


def test_explains_a_missing_build(client: Client, settings: Settings, tmp_path: Path) -> None:
    settings.FRONTEND_DIR = tmp_path  # nothing built

    response = client.get("/")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert b"pnpm build" in response.content
