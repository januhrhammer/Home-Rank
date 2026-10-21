"""Login rate limiting: after too many failed attempts, a client is blocked for a while."""

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from homerank.accounts.models import User

if TYPE_CHECKING:  # the test client's response type exists only in django-stubs, not at runtime
    from django.test.client import _MonkeyPatchedWSGIResponse as TestResponse

PASSWORD = "correct horse battery staple"
WRONG_PASSWORD = "not the right password"


@pytest.fixture
def alice(db: None) -> User:
    return User.objects.create_user(username="alice", password=PASSWORD, is_staff=True)


def api_login(client: Client, password: str) -> "TestResponse":
    return client.post(
        "/api/v1/auth/login",
        {"username": "alice", "password": password},
        content_type="application/json",
    )


def admin_login(client: Client, password: str) -> "TestResponse":
    return client.post(reverse("admin:login"), {"username": "alice", "password": password})


def test_api_login_is_blocked_after_too_many_failures(client: Client, alice: User) -> None:
    for _ in range(settings.AXES_FAILURE_LIMIT - 1):
        assert api_login(client, WRONG_PASSWORD).status_code == HTTPStatus.UNAUTHORIZED

    blocked = api_login(client, WRONG_PASSWORD)  # the failure that reaches the limit
    even_the_right_password = api_login(client, PASSWORD)

    assert blocked.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert blocked["Content-Type"] == "application/problem+json"
    assert blocked.json()["detail"].endswith("Try again in 15 minutes.")
    assert even_the_right_password.status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_a_successful_login_resets_the_count(client: Client, alice: User) -> None:
    for _ in range(settings.AXES_FAILURE_LIMIT - 1):
        api_login(client, WRONG_PASSWORD)

    api_login(client, PASSWORD)

    assert api_login(client, WRONG_PASSWORD).status_code == HTTPStatus.UNAUTHORIZED


def test_admin_login_is_blocked_too(client: Client, alice: User) -> None:
    for _ in range(settings.AXES_FAILURE_LIMIT):
        response = admin_login(client, WRONG_PASSWORD)

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert response["Content-Type"] == "text/plain"
