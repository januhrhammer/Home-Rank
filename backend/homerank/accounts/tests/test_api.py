from http import HTTPStatus

import pytest
from django.conf import settings
from django.test import Client

from homerank.accounts.models import User


def test_csrf_endpoint_sets_the_csrf_cookie(client: Client) -> None:
    response = client.get("/api/v1/auth/csrf")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert settings.CSRF_COOKIE_NAME in response.cookies


def test_me_requires_login(client: Client) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response["Content-Type"] == "application/problem+json"


@pytest.mark.django_db
def test_me_returns_the_logged_in_user(client: Client) -> None:
    alice = User.objects.create_user(username="alice", email="alice@example.org")
    client.force_login(alice)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": alice.id,
        "username": "alice",
        "email": "alice@example.org",
        "is_staff": False,
    }
