from http import HTTPStatus
from typing import NoReturn

import pytest
from django.db import OperationalError
from django.test import Client

from homerank.core import health


class UnreachableDatabase:
    """Stands in for django.db.connection when the database is down."""

    def cursor(self) -> NoReturn:
        raise OperationalError


# No django_db marker: pytest-django blocks database access, so this fails if healthz used it.
def test_healthz_does_not_need_the_database(client: Client) -> None:
    response = client.get("/healthz")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readyz_is_ok_when_the_database_is_reachable(client: Client) -> None:
    response = client.get("/readyz")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_readyz_is_unavailable_when_the_database_is_down(
    client: Client, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(health, "connection", UnreachableDatabase())

    response = client.get("/readyz")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {"status": "unavailable"}
    assert "database unreachable" in caplog.text


def test_health_checks_only_answer_get_and_head(client: Client) -> None:
    assert client.post("/healthz").status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert client.head("/healthz").status_code == HTTPStatus.OK
