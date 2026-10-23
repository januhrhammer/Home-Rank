"""The reference API: databases, their games, and copying a game into your own."""

from http import HTTPStatus

import pytest
from django.test import Client

from homerank.accounts.models import User
from homerank.games.models import Collection, Game
from homerank.reference.models import ReferenceDatabase

pytestmark = pytest.mark.django_db

AS_JSON = "application/json"


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


@pytest.fixture
def alice_client(client: Client, alice: User) -> Client:
    client.force_login(alice)
    return client


def test_lists_the_databases_for_every_user(
    alice_client: Client, masters: ReferenceDatabase
) -> None:
    body = alice_client.get("/api/v1/reference/databases").json()

    assert [(d["name"], d["game_count"], d["status"]) for d in body] == [("Masters", 2, "ready")]


def test_lists_a_databases_games_with_filters(
    alice_client: Client, masters: ReferenceDatabase
) -> None:
    url = f"/api/v1/reference/databases/{masters.pk}/games"

    everything = alice_client.get(url).json()
    morphy = alice_client.get(f"{url}?player=morphy").json()
    rated = alice_client.get(f"{url}?min_rating=2000").json()

    assert [g["white"] for g in everything["items"]] == ["Anna", "Morphy, Paul"]  # newest first
    assert [g["white"] for g in morphy["items"]] == ["Morphy, Paul"]
    assert rated["items"] == []  # the Duke had no rating


def test_a_game_comes_with_its_pgn(alice_client: Client, masters: ReferenceDatabase) -> None:
    body = alice_client.get(f"/api/v1/reference/databases/{masters.pk}/games/2").json()

    assert body["white"] == "Anna"
    assert '[Result "0-1"]' in body["pgn"]
    assert "1. f3 e5 2. g4 Qh4# 0-1" in body["pgn"]


def test_copies_a_game_into_your_games_and_a_collection(
    alice_client: Client, alice: User, masters: ReferenceDatabase
) -> None:
    collection = Collection.objects.create(user=alice, name="Classics")
    url = f"/api/v1/reference/databases/{masters.pk}/games/1/copy"

    first = alice_client.post(url, {"collection": collection.pk}, content_type=AS_JSON)
    again = alice_client.post(url, {}, content_type=AS_JSON)

    assert first.status_code == HTTPStatus.CREATED
    assert again.status_code == HTTPStatus.OK  # you have it already
    assert first.json()["game_id"] == again.json()["game_id"]
    copy = Game.objects.get(user=alice)
    assert (copy.white, copy.event, copy.ply_count) == ("Morphy, Paul", "Paris", 6)
    assert list(collection.games.all()) == [copy]


def test_unknown_databases_and_games_are_not_found(
    alice_client: Client, masters: ReferenceDatabase
) -> None:
    assert alice_client.get("/api/v1/reference/databases/999/games").status_code == 404  # noqa: PLR2004
    url = f"/api/v1/reference/databases/{masters.pk}/games/999"
    assert alice_client.get(url).status_code == HTTPStatus.NOT_FOUND


# Isolation: a copy belongs to the user who made it, into their own collections only.


def test_copies_into_someone_elses_collection_are_refused(
    alice_client: Client, masters: ReferenceDatabase
) -> None:
    bob = User.objects.create_user(username="bob")
    bobs = Collection.objects.create(user=bob, name="Bob's")

    response = alice_client.post(
        f"/api/v1/reference/databases/{masters.pk}/games/1/copy",
        {"collection": bobs.pk},
        content_type=AS_JSON,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert not Game.objects.exists()


def test_requires_login(client: Client) -> None:
    assert client.get("/api/v1/reference/databases").status_code == HTTPStatus.UNAUTHORIZED
