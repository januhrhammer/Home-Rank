"""The novelty search API (ADR 0022)."""

from http import HTTPStatus
from typing import Any

import chess
import pytest
from django.test import Client

from homerank.accounts.models import User
from homerank.engine.tests.scripted import ENGINE, MODEL, ScriptedEngine, ScriptedModel
from homerank.novelty.models import NoveltySearch, SearchStatus
from homerank.novelty.services import run_search

pytestmark = pytest.mark.django_db

AS_JSON = "application/json"
URL = "/api/v1/novelty"


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


@pytest.fixture
def alice_client(client: Client, alice: User) -> Client:
    client.force_login(alice)
    return client


def post(client: Client, url: str, data: dict[str, Any]) -> Any:
    return client.post(url, data, content_type=AS_JSON)


SEARCH = {"fen": chess.STARTING_FEN, "side": "white", "rating": 1800, "rating_kind": "fide"}


def test_a_search_is_started_listed_and_shown_with_its_tries(alice_client: Client) -> None:
    created = post(alice_client, f"{URL}/searches", {**SEARCH, "label": "Test", "limit_minutes": 5})
    search_id = created.json()["id"]
    run_search(search_id, engines=[ScriptedEngine(ENGINE)], model=ScriptedModel(MODEL))
    listed = alice_client.get(f"{URL}/searches").json()
    shown = alice_client.get(f"{URL}/searches/{search_id}").json()

    assert created.status_code == HTTPStatus.CREATED
    assert {k: created.json()[k] for k in ("status", "elo", "budget_cp", "limit_minutes")} == {
        "status": "queued",
        "elo": 1962,  # FIDE 1800
        "budget_cp": 150,
        "limit_minutes": 5,
    }
    assert [s["id"] for s in listed["items"]] == [search_id]
    assert (shown["status"], shown["own_moves"]) == ("done", 4)
    (first,) = shown["tries"]
    assert (first["san"], first["best_san"], first["line"]) == ("g4", "e4", [])
    assert first["refutation"][0]["san"] == "d5"


def test_the_form_previews_the_rating_maia_plays_at(alice_client: Client) -> None:
    def elo(**query: str | int) -> Any:
        return alice_client.get(f"{URL}/rating", query).json()["elo"]

    assert elo(rating=1500, kind="dwz") == 1750  # noqa: PLR2004
    assert elo(rating=1700) == 1875  # FIDE by default  # noqa: PLR2004
    assert elo(rating=1700, kind="lichess") == 1700  # noqa: PLR2004


@pytest.mark.parametrize(
    "bad",
    [
        {"elo": 3000},  # beyond Maia's ratings
        {"limit_minutes": 0},
        {"budget_cp": 900},
        {"side": "red"},
    ],
)
def test_invalid_searches_are_refused(alice_client: Client, bad: dict[str, Any]) -> None:
    assert post(alice_client, f"{URL}/searches", {**SEARCH, **bad}).status_code == (
        HTTPStatus.UNPROCESSABLE_ENTITY
    )
    assert not NoveltySearch.objects.exists()


def test_a_search_is_cancelled_then_deleted(alice_client: Client) -> None:
    search_id = post(alice_client, f"{URL}/searches", SEARCH).json()["id"]

    too_early = alice_client.delete(f"{URL}/searches/{search_id}")
    cancelled = post(alice_client, f"{URL}/searches/{search_id}/cancel", {})
    again = post(alice_client, f"{URL}/searches/{search_id}/cancel", {})
    deleted = alice_client.delete(f"{URL}/searches/{search_id}")

    assert too_early.status_code == HTTPStatus.CONFLICT
    assert cancelled.json()["status"] == SearchStatus.CANCELLED
    assert again.status_code == HTTPStatus.CONFLICT
    assert deleted.status_code == HTTPStatus.NO_CONTENT
    assert not NoveltySearch.objects.exists()


def test_someone_elses_search_is_not_found(alice_client: Client, client: Client) -> None:
    search_id = post(alice_client, f"{URL}/searches", SEARCH).json()["id"]
    client.force_login(User.objects.create_user(username="bob"))

    responses = [
        client.get(f"{URL}/searches/{search_id}"),
        post(client, f"{URL}/searches/{search_id}/cancel", {}),
        client.delete(f"{URL}/searches/{search_id}"),
    ]

    assert {r.status_code for r in responses} == {HTTPStatus.NOT_FOUND}
    assert client.get(f"{URL}/searches").json()["items"] == []
    assert NoveltySearch.objects.get().status == SearchStatus.QUEUED


def test_logged_out_is_unauthorized(client: Client) -> None:
    assert client.get(f"{URL}/searches").status_code == HTTPStatus.UNAUTHORIZED
