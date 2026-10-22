"""Collections and tags. They work alike, so most tests run for both."""

import itertools
from http import HTTPStatus
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from homerank.accounts.models import User
from homerank.games.models import Collection, Game, Tag

_hashes = itertools.count()

pytestmark = pytest.mark.django_db


@pytest.fixture(params=["collections", "tags"])
def kind(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def model_of(kind: str) -> type[Collection] | type[Tag]:
    return Collection if kind == "collections" else Tag


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


@pytest.fixture
def bob() -> User:
    return User.objects.create_user(username="bob")


@pytest.fixture
def alice_client(client: Client, alice: User) -> Client:
    client.force_login(alice)
    return client


def make_game(user: User) -> Game:
    return Game.objects.create(
        user=user,
        source=Game.Source.PGN,
        pgn="*\n",
        result="*",
        date_pgn="????.??.??",
        time_class="unknown",
        ply_count=0,
        dedup_hash=f"{next(_hashes):064}",
    )


def create(client: Client, kind: str, name: str) -> Any:
    return client.post(f"/api/v1/{kind}", {"name": name}, content_type="application/json")


def test_creates_one(alice_client: Client, alice: User, kind: str) -> None:
    response = create(alice_client, kind, "  Najdorf  ")

    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert (body["name"], body["game_count"]) == ("Najdorf", 0)  # trimmed
    assert model_of(kind).objects.get(user=alice).name == "Najdorf"


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_refuses_empty_or_long_names(alice_client: Client, kind: str, name: str) -> None:
    response = create(alice_client, kind, name)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_names_are_unique_whatever_their_case(alice_client: Client, kind: str) -> None:
    create(alice_client, kind, "Najdorf")

    response = create(alice_client, kind, "NAJDORF")

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["detail"] == 'You already have one called "NAJDORF".'


def test_other_users_may_use_the_same_name(alice_client: Client, bob: User, kind: str) -> None:
    model_of(kind).objects.create(user=bob, name="Najdorf")

    assert create(alice_client, kind, "Najdorf").status_code == HTTPStatus.CREATED


def test_lists_them_by_name_with_their_games(alice_client: Client, alice: User, kind: str) -> None:
    model = model_of(kind)
    later = model.objects.create(user=alice, name="Zugzwang")
    earlier = model.objects.create(user=alice, name="endgames")
    earlier.games.add(make_game(alice), make_game(alice))

    page = alice_client.get(f"/api/v1/{kind}").json()

    # Case doesn't count. (The test database's collation ignores case anyway; on a server with
    # the C collation, "Zugzwang" would come first without the Lower() in selectors.groups.)
    assert [(item["name"], item["game_count"]) for item in page["items"]] == [
        ("endgames", 2),
        ("Zugzwang", 0),
    ]
    assert page["total"] == len([earlier, later])


def test_renames_one(alice_client: Client, alice: User, kind: str) -> None:
    group = model_of(kind).objects.create(user=alice, name="Endgames")

    response = alice_client.patch(
        f"/api/v1/{kind}/{group.pk}", {"name": "Rook endgames"}, content_type="application/json"
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "Rook endgames"


def test_renaming_to_a_taken_name_is_refused(alice_client: Client, alice: User, kind: str) -> None:
    model = model_of(kind)
    model.objects.create(user=alice, name="Endgames")
    group = model.objects.create(user=alice, name="Openings")

    response = alice_client.patch(
        f"/api/v1/{kind}/{group.pk}", {"name": "endgames"}, content_type="application/json"
    )

    assert response.status_code == HTTPStatus.CONFLICT
    group.refresh_from_db()
    assert group.name == "Openings"


def test_deleting_one_keeps_its_games(alice_client: Client, alice: User, kind: str) -> None:
    group = model_of(kind).objects.create(user=alice, name="Endgames")
    game = make_game(alice)
    group.games.add(game)

    response = alice_client.delete(f"/api/v1/{kind}/{group.pk}")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert not model_of(kind).objects.exists()
    assert Game.objects.filter(pk=game.pk).exists()


def test_adds_and_removes_games(alice_client: Client, alice: User, kind: str) -> None:
    group = model_of(kind).objects.create(user=alice, name="Endgames")
    first, second, third = make_game(alice), make_game(alice), make_game(alice)
    games_url = f"/api/v1/{kind}/{group.pk}/games"

    added = alice_client.post(
        games_url, {"game_ids": [first.pk, second.pk, third.pk]}, content_type="application/json"
    )
    again = alice_client.post(games_url, {"game_ids": [first.pk]}, content_type="application/json")
    removed = alice_client.delete(f"{games_url}?game_ids={first.pk}&game_ids={third.pk}")

    assert added.json()["game_count"] == len([first, second, third])
    assert again.json()["game_count"] == len([first, second, third])  # adding twice is harmless
    assert removed.json()["game_count"] == 1
    assert list(group.games.all()) == [second]


def test_games_show_their_tags_and_collections(alice_client: Client, alice: User) -> None:
    game = make_game(alice)
    Tag.objects.create(user=alice, name="won").games.add(game)
    Tag.objects.create(user=alice, name="Blunder").games.add(game)
    Collection.objects.create(user=alice, name="Club games").games.add(game)

    (item,) = alice_client.get("/api/v1/games").json()["items"]
    detail = alice_client.get(f"/api/v1/games/{game.pk}").json()

    assert [tag["name"] for tag in item["tags"]] == ["Blunder", "won"]  # by name
    assert [tag["name"] for tag in detail["tags"]] == ["Blunder", "won"]
    assert [collection["name"] for collection in detail["collections"]] == ["Club games"]


def test_tags_dont_add_queries_per_game(alice_client: Client, alice: User) -> None:
    tag = Tag.objects.create(user=alice, name="won")
    tag.games.add(make_game(alice))
    with CaptureQueriesContext(connection) as one_game:
        alice_client.get("/api/v1/games")

    tag.games.add(*[make_game(alice) for _ in range(20)])
    with CaptureQueriesContext(connection) as many_games:
        alice_client.get("/api/v1/games")

    assert len(many_games) == len(one_game)


def test_collections_have_a_description(alice_client: Client) -> None:
    created = alice_client.post(
        "/api/v1/collections",
        {"name": "Club games", "description": "Hamburg league 2024"},
        content_type="application/json",
    ).json()

    changed = alice_client.patch(
        f"/api/v1/collections/{created['id']}",
        {"description": "Hamburg league 2024/25"},
        content_type="application/json",
    ).json()

    assert (changed["name"], changed["description"]) == ("Club games", "Hamburg league 2024/25")


# Isolation: users only ever see and change their own collections and tags.


def test_lists_only_your_own(alice_client: Client, alice: User, bob: User, kind: str) -> None:
    model_of(kind).objects.create(user=alice, name="mine")
    model_of(kind).objects.create(user=bob, name="bobs")

    page = alice_client.get(f"/api/v1/{kind}").json()

    assert [item["name"] for item in page["items"]] == ["mine"]


def test_someone_elses_is_not_found(alice_client: Client, bob: User, kind: str) -> None:
    bobs = model_of(kind).objects.create(user=bob, name="bobs")
    url = f"/api/v1/{kind}/{bobs.pk}"
    as_json = "application/json"

    responses = [
        alice_client.patch(url, {"name": "taken over"}, content_type=as_json),
        alice_client.delete(url),
        alice_client.post(f"{url}/games", {"game_ids": [1]}, content_type=as_json),
        alice_client.delete(f"{url}/games?game_ids=1"),
    ]

    assert [r.status_code for r in responses] == [HTTPStatus.NOT_FOUND] * len(responses)
    bobs.refresh_from_db()
    assert bobs.name == "bobs"


def test_someone_elses_games_cant_be_added(
    alice_client: Client, alice: User, bob: User, kind: str
) -> None:
    group = model_of(kind).objects.create(user=alice, name="mine")
    mine, bobs = make_game(alice), make_game(bob)

    response = alice_client.post(
        f"/api/v1/{kind}/{group.pk}/games",
        {"game_ids": [mine.pk, bobs.pk]},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert not group.games.exists()  # all or nothing


def test_requires_login(client: Client, kind: str) -> None:
    assert client.get(f"/api/v1/{kind}").status_code == HTTPStatus.UNAUTHORIZED
