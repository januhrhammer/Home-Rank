from http import HTTPStatus

import pytest
from django.http import Http404, HttpRequest
from django.test import Client, RequestFactory
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from ninja.testing import TestClient

from config.api import api
from homerank.core.errors import register_problem_handlers

CONFLICT_MESSAGE = "This game has already been imported."
INTERNAL_DETAIL = "secret internal detail"

# A small API with one endpoint per kind of error, using the same handlers as the real API.
errors_api = NinjaAPI(urls_namespace="errors-test")
register_problem_handlers(errors_api)
client = TestClient(errors_api)


class Rating(Schema):
    elo: int


@errors_api.post("/validation")
def invalid_input(request: HttpRequest, rating: Rating) -> None: ...


@errors_api.get("/http-error")
def http_error(request: HttpRequest) -> None:
    raise HttpError(HTTPStatus.CONFLICT, CONFLICT_MESSAGE)


@errors_api.get("/not-found")
def not_found(request: HttpRequest) -> None:
    raise Http404


@errors_api.get("/crash")
def crash(request: HttpRequest) -> None:
    raise RuntimeError(INTERNAL_DETAIL)


def test_validation_errors_list_each_invalid_field() -> None:
    response = client.post("/validation", json={"elo": "not a number"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response["Content-Type"] == "application/problem+json"
    problem = response.json()
    assert problem["title"] == "Unprocessable Entity"
    assert problem["errors"][0]["loc"] == ["body", "rating", "elo"]


def test_http_errors_keep_their_status_and_message() -> None:
    response = client.get("/http-error")

    assert response.json() == {
        "type": "about:blank",
        "title": "Conflict",
        "status": 409,
        "detail": CONFLICT_MESSAGE,
    }


def test_not_found_is_a_problem_too() -> None:
    response = client.get("/not-found")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["title"] == "Not Found"


def test_unexpected_errors_are_logged_but_not_revealed(caplog: pytest.LogCaptureFixture) -> None:
    response = client.get("/crash")

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert INTERNAL_DETAIL not in response.content.decode()
    assert INTERNAL_DETAIL in caplog.text


def test_the_real_api_answers_with_problem_details(rf: RequestFactory) -> None:
    response = api.on_exception(rf.get("/api/v1/"), Http404())

    assert response["Content-Type"] == "application/problem+json"


def test_unknown_api_urls_get_a_problem_not_an_html_page() -> None:
    # A POST with CSRF checks on: it must get the 404, not Django's CSRF failure page.
    django_client = Client(enforce_csrf_checks=True)

    response = django_client.post("/api/v1/no-such-endpoint")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response["Content-Type"] == "application/problem+json"
