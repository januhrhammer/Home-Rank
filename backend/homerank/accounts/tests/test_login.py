"""Login and logout through the API, with CSRF checks enforced as in a real browser."""

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.conf import settings
from django.test import Client

from homerank.accounts.models import User

if TYPE_CHECKING:  # the test client's response type exists only in django-stubs, not at runtime
    from django.test.client import _MonkeyPatchedWSGIResponse as TestResponse

PASSWORD = "correct horse battery staple"


@pytest.fixture
def browser() -> Client:
    """A test client that, like a real browser, is subject to CSRF checks."""
    return Client(enforce_csrf_checks=True)


@pytest.fixture
def alice(db: None) -> User:
    return User.objects.create_user(username="alice", password=PASSWORD)


def fetch_csrf_token(client: Client) -> str:
    client.get("/api/v1/auth/csrf")
    return client.cookies[settings.CSRF_COOKIE_NAME].value


def log_in(client: Client, username: str, password: str, csrf_token: str | None) -> "TestResponse":
    headers = {"X-CSRFToken": csrf_token} if csrf_token else {}
    return client.post(
        "/api/v1/auth/login",
        {"username": username, "password": password},
        content_type="application/json",
        headers=headers,
    )


def test_login_starts_a_session(browser: Client, alice: User) -> None:
    response = log_in(browser, "alice", PASSWORD, fetch_csrf_token(browser))

    assert response.status_code == HTTPStatus.OK
    assert response.json()["username"] == "alice"
    assert browser.get("/api/v1/auth/me").status_code == HTTPStatus.OK


def test_login_without_csrf_token_is_rejected(browser: Client, alice: User) -> None:
    response = log_in(browser, "alice", PASSWORD, csrf_token=None)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response["Content-Type"] == "application/problem+json"
    assert browser.get("/api/v1/auth/me").status_code == HTTPStatus.UNAUTHORIZED


def test_wrong_password_and_unknown_user_get_the_same_answer(browser: Client, alice: User) -> None:
    token = fetch_csrf_token(browser)

    wrong_password = log_in(browser, "alice", "not the right password", token)
    unknown_user = log_in(browser, "mallory", PASSWORD, token)

    assert wrong_password.status_code == HTTPStatus.UNAUTHORIZED
    assert wrong_password.json() == unknown_user.json()


def test_inactive_users_cannot_log_in(browser: Client, alice: User) -> None:
    alice.is_active = False
    alice.save()

    response = log_in(browser, "alice", PASSWORD, fetch_csrf_token(browser))

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_login_issues_a_new_csrf_token(browser: Client, alice: User) -> None:
    token_before = fetch_csrf_token(browser)

    log_in(browser, "alice", PASSWORD, token_before)

    assert browser.cookies[settings.CSRF_COOKIE_NAME].value != token_before


def test_logout_ends_the_session(browser: Client, alice: User) -> None:
    log_in(browser, "alice", PASSWORD, fetch_csrf_token(browser))
    token_after_login = browser.cookies[settings.CSRF_COOKIE_NAME].value

    response = browser.post("/api/v1/auth/logout", headers={"X-CSRFToken": token_after_login})

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert browser.get("/api/v1/auth/me").status_code == HTTPStatus.UNAUTHORIZED


def test_logout_without_csrf_token_is_rejected(browser: Client, alice: User) -> None:
    # Endpoints that require login get CSRF protection from the API-wide django_auth.
    browser.force_login(alice)

    response = browser.post("/api/v1/auth/logout")

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert browser.get("/api/v1/auth/me").status_code == HTTPStatus.OK
