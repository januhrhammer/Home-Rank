import datetime
import itertools
from http import HTTPStatus
from typing import Any

import chess
import chess.polyglot
import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from homerank.accounts.models import User
from homerank.chesslib.positions import as_bigint
from homerank.games.models import Collection, Game, GamePosition, ImportRun, Tag

GAMES = "/api/v1/games"
_hashes = itertools.count()

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


@pytest.fixture
def alice_client(client: Client, alice: User) -> Client:
    client.force_login(alice)
    return client


def make_game(user: User, **fields: Any) -> Game:
    values = {
        "source": Game.Source.PGN,
        "pgn": "1. e4 e5 *\n",
        "white": "Anna",
        "black": "Ben",
        "result": "*",
        "date": datetime.date(2024, 1, 1),
        "date_pgn": "2024.01.01",
        "time_class": "blitz",
        "ply_count": 2,
        "dedup_hash": f"{next(_hashes):064}",
        **fields,
    }
    return Game.objects.create(user=user, **values)


def with_positions(game: Game, sans: str) -> Game:
    """Store the positions of the game's moves, as an import does."""
    board = chess.Board()
    rows = [
        GamePosition(
            game=game, user=game.user, ply=0, zobrist=as_bigint(chess.polyglot.zobrist_hash(board))
        )
    ]
    for ply, san in enumerate(sans.split(), start=1):
        board.push_san(san)
        zobrist = as_bigint(chess.polyglot.zobrist_hash(board))
        rows.append(GamePosition(game=game, user=game.user, ply=ply, zobrist=zobrist))
    GamePosition.objects.bulk_create(rows)
    return game


def listed(client: Client, **params: Any) -> list[int]:
    """The ids of the games the list returns, in its order."""
    response = client.get(GAMES, params)
    assert response.status_code == HTTPStatus.OK, response.json()
    return [game["id"] for game in response.json()["items"]]


def test_lists_games_newest_first(alice_client: Client, alice: User) -> None:
    old = make_game(alice, date=datetime.date(2020, 5, 1))
    new = make_game(alice, date=datetime.date(2024, 5, 1))
    undated = make_game(alice, date=None, date_pgn="????.??.??")

    assert listed(alice_client) == [new.pk, old.pk, undated.pk]  # unknown dates last


def test_items_have_the_headers_but_not_the_moves(alice_client: Client, alice: User) -> None:
    make_game(alice, white="Carlsen, Magnus", white_elo=2830, eco="C65", user_color="white")

    (item,) = alice_client.get(GAMES).json()["items"]

    assert (item["white"], item["white_elo"], item["eco"]) == ("Carlsen, Magnus", 2830, "C65")
    assert (item["user_color"], item["date_pgn"], item["time_class"]) == (
        "white",
        "2024.01.01",
        "blitz",
    )
    assert "pgn" not in item


def test_items_are_named_after_the_opening_their_moves_reach(
    alice_client: Client, alice: User
) -> None:
    # A Chess.com game: ECO only. A game whose positions the list doesn't name (here: none
    # stored) keeps the name its file gave it (ADR 0021).
    ruy = with_positions(make_game(alice, eco="C60", opening=""), "e4 e5 Nf3 Nc6 Bb5 a6 Ba4")
    unnamed = make_game(alice, eco="A00", opening="Odd start")

    items = {g["id"]: g for g in alice_client.get(GAMES).json()["items"]}

    assert (items[ruy.pk]["eco"], items[ruy.pk]["opening"]) == (
        "C70",
        "Ruy Lopez: Morphy Defense",
    )
    assert (items[unnamed.pk]["eco"], items[unnamed.pk]["opening"]) == ("A00", "Odd start")


def test_pages_have_a_total(alice_client: Client, alice: User) -> None:
    for day in range(1, 4):
        make_game(alice, date=datetime.date(2024, 1, day))

    page = alice_client.get(GAMES, {"limit": 2}).json()

    assert len(page["items"]) == len(["first", "second"])
    assert page["total"] == len(["first", "second", "third"])


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("date", ["2020", "2024", "none"]),
        ("-date", ["2024", "2020", "none"]),  # unknown dates last both ways
        ("white", ["2024", "2020", "none"]),
        ("-white_elo", ["2020", "2024", "none"]),
    ],
)
def test_sorts(alice_client: Client, alice: User, sort: str, expected: list[str]) -> None:
    games = {
        "2020": make_game(alice, date=datetime.date(2020, 1, 1), white="Bob", white_elo=2000),
        "2024": make_game(alice, date=datetime.date(2024, 1, 1), white="Anna", white_elo=1500),
        "none": make_game(alice, date=None, white="Cleo", white_elo=None),
    }

    assert listed(alice_client, sort=sort) == [games[name].pk for name in expected]


def test_equal_values_keep_a_stable_order(alice_client: Client, alice: User) -> None:
    """Sorting by id as well keeps pages from overlapping when values are equal."""
    first, second = make_game(alice), make_game(alice)

    assert listed(alice_client, sort="date") == [first.pk, second.pk]
    assert listed(alice_client, sort="-date") == [second.pk, first.pk]


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "pgn"},
        {"sort": "-user"},
        {"eco": "F12"},
        {"eco": "B123"},
        {"limit": 0},
        {"color": "green"},
        {"date_from": "yesterday"},
    ],
)
def test_rejects_invalid_parameters(alice_client: Client, params: dict[str, Any]) -> None:
    assert alice_client.get(GAMES, params).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_filters_by_player_as_white_or_black(alice_client: Client, alice: User) -> None:
    as_white = make_game(alice, white="Carlsen, Magnus", black="Anna")
    as_black = make_game(alice, white="Anna", black="Carlsen, Magnus")
    make_game(alice, white="Anna", black="Ben")

    assert set(listed(alice_client, player="carlsen")) == {as_white.pk, as_black.pk}


def test_filters_by_the_users_side(alice_client: Client, alice: User) -> None:
    white = make_game(alice, user_color="white")
    black = make_game(alice, user_color="black")
    make_game(alice, user_color="")

    assert listed(alice_client, color="white") == [white.pk]
    assert listed(alice_client, color="black") == [black.pk]


def test_filters_by_result(alice_client: Client, alice: User) -> None:
    draw = make_game(alice, result="1/2-1/2")
    make_game(alice, result="1-0")

    assert listed(alice_client, result="1/2-1/2") == [draw.pk]


def test_filters_by_outcome_from_the_users_side(alice_client: Client, alice: User) -> None:
    won_white = make_game(alice, user_color="white", result="1-0")
    won_black = make_game(alice, user_color="black", result="0-1")
    lost = make_game(alice, user_color="white", result="0-1")
    drawn = make_game(alice, user_color="black", result="1/2-1/2")
    make_game(alice, user_color="", result="1-0")  # not the user's game
    make_game(alice, user_color="", result="1/2-1/2")

    assert set(listed(alice_client, outcome="win")) == {won_white.pk, won_black.pk}
    assert listed(alice_client, outcome="loss") == [lost.pk]
    assert listed(alice_client, outcome="draw") == [drawn.pk]


def test_filters_by_dates(alice_client: Client, alice: User) -> None:
    make_game(alice, date=datetime.date(2023, 12, 31))
    inside = make_game(alice, date=datetime.date(2024, 6, 1))
    make_game(alice, date=datetime.date(2025, 1, 1))
    make_game(alice, date=None)

    assert listed(alice_client, date_from="2024-01-01", date_to="2024-12-31") == [inside.pk]


def test_filters_by_eco_and_its_start(alice_client: Client, alice: User) -> None:
    b23 = make_game(alice, eco="B23")
    b90 = make_game(alice, eco="B90")
    make_game(alice, eco="C45")

    assert set(listed(alice_client, eco="B")) == {b23.pk, b90.pk}
    assert listed(alice_client, eco="b2") == [b23.pk]
    assert listed(alice_client, eco="B23") == [b23.pk]


def test_filters_by_opening_name(alice_client: Client, alice: User) -> None:
    sicilian = make_game(alice, opening="Sicilian Defense: Najdorf Variation")
    make_game(alice, opening="French Defense")

    assert listed(alice_client, opening="najdorf") == [sicilian.pk]


def test_filters_by_source_and_time_class(alice_client: Client, alice: User) -> None:
    lichess_rapid = make_game(alice, source=Game.Source.LICHESS, source_id="x", time_class="rapid")
    make_game(alice, source=Game.Source.LICHESS, source_id="y", time_class="blitz")
    make_game(alice, source=Game.Source.PGN, time_class="rapid")

    assert listed(alice_client, source="lichess", time_class="rapid") == [lichess_rapid.pk]


def test_filters_by_tag_collection_and_import(alice_client: Client, alice: User) -> None:
    run = ImportRun.objects.create(user=alice, file_name="club.pgn", file_size=1)
    tagged, collected, imported = (
        make_game(alice),
        make_game(alice),
        make_game(alice, import_run=run),
    )
    make_game(alice)
    tag = Tag.objects.create(user=alice, name="brilliant")
    tag.games.add(tagged)
    collection = Collection.objects.create(user=alice, name="Openings")
    collection.games.add(collected)

    assert listed(alice_client, tag=tag.pk) == [tagged.pk]
    assert listed(alice_client, collection=collection.pk) == [collected.pk]
    assert listed(alice_client, import_run=run.pk) == [imported.pk]


def test_the_number_of_queries_doesnt_grow_with_the_games(
    alice_client: Client, alice: User
) -> None:
    with_positions(make_game(alice), "e4 e5")
    with CaptureQueriesContext(connection) as one_game:
        alice_client.get(GAMES)

    for _ in range(25):
        with_positions(make_game(alice), "d4 d5")
    with CaptureQueriesContext(connection) as many_games:
        alice_client.get(GAMES)

    assert len(many_games) == len(one_game)


def test_the_list_doesnt_load_the_moves(alice_client: Client, alice: User) -> None:
    """A game's PGN text can be long, and the list doesn't show it."""
    make_game(alice)

    with CaptureQueriesContext(connection) as queries:
        alice_client.get(GAMES)

    game_queries = [q["sql"] for q in queries if 'FROM "games_game"' in q["sql"]]
    assert game_queries
    assert not any('"games_game"."pgn"' in sql for sql in game_queries)


# Isolation: users only ever see their own games.


def test_lists_only_your_own_games(alice_client: Client, alice: User) -> None:
    mine = make_game(alice)
    make_game(User.objects.create_user(username="bob"))

    page = alice_client.get(GAMES).json()

    assert [game["id"] for game in page["items"]] == [mine.pk]
    assert page["total"] == 1


def test_someone_elses_tag_collection_or_import_shows_nothing(
    alice_client: Client, alice: User
) -> None:
    make_game(alice)
    bob = User.objects.create_user(username="bob")
    bobs_run = ImportRun.objects.create(user=bob, file_name="bob.pgn", file_size=1)
    bobs_game = make_game(bob, import_run=bobs_run)
    bobs_tag = Tag.objects.create(user=bob, name="brilliant")
    bobs_tag.games.add(bobs_game)
    bobs_collection = Collection.objects.create(user=bob, name="Openings")
    bobs_collection.games.add(bobs_game)

    assert listed(alice_client, tag=bobs_tag.pk) == []
    assert listed(alice_client, collection=bobs_collection.pk) == []
    assert listed(alice_client, import_run=bobs_run.pk) == []


def test_the_list_requires_login(client: Client) -> None:
    assert client.get(GAMES).status_code == HTTPStatus.UNAUTHORIZED
