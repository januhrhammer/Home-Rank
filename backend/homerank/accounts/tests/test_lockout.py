"""Login rate limiting: after too many failed attempts, a client is blocked for a while."""

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.conf import settings
from django.test import Client, RequestFactory
from django.urls import reverse
from pytest_django import Settings

from homerank.accounts.lockout import client_ip
from homerank.accounts.models import User

if TYPE_CHECKING:  # the test client's response type exists only in django-stubs, not at runtime
    from django.test.client import _MonkeyPatchedWSGIResponse as TestResponse

PASSWORD = "correct horse battery staple"
WRONG_PASSWORD = "not the right password"


@pytest.fixture
def alice(db: None) -> User:
    return User.objects.create_user(username="alice", password=PASSWORD, is_staff=True)


def api_login(client: Client, password: str, forwarded_for: str | None = None) -> "TestResponse":
    headers = {"X-Forwarded-For": forwarded_for} if forwarded_for else {}
    return client.post(
        "/api/v1/auth/login",
        {"username": "alice", "password": password},
        content_type="application/json",
        headers=headers,
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


# The test client's own address (REMOTE_ADDR, 127.0.0.1) plays the reverse proxy below.


def test_behind_a_proxy_each_visitor_has_their_own_count(
    client: Client, alice: User, settings: Settings
) -> None:
    settings.TRUST_PROXY_HEADERS = True
    for _ in range(settings.AXES_FAILURE_LIMIT):
        api_login(client, WRONG_PASSWORD, forwarded_for="203.0.113.7")  # an attacker

    someone_else = api_login(client, PASSWORD, forwarded_for="198.51.100.2")

    assert someone_else.status_code == HTTPStatus.OK


def test_without_a_trusted_proxy_a_faked_address_does_not_dodge_the_block(
    client: Client, alice: User
) -> None:
    for attempt in range(settings.AXES_FAILURE_LIMIT - 1):
        api_login(client, WRONG_PASSWORD, forwarded_for=f"203.0.113.{attempt}")

    blocked = api_login(client, WRONG_PASSWORD, forwarded_for="198.51.100.2")

    assert blocked.status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_only_the_address_the_proxy_saw_counts(rf: RequestFactory, settings: Settings) -> None:
    settings.TRUST_PROXY_HEADERS = True
    # The visitor sent a made-up X-Forwarded-For; the proxy appended the address it really saw.
    request = rf.get("/", headers={"X-Forwarded-For": "10.0.0.1, 203.0.113.7"})

    assert client_ip(request) == "203.0.113.7"
