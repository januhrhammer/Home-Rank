import datetime
import itertools
from http import HTTPStatus
from typing import Any

import pytest
from django.test import Client

from homerank.accounts.models import User
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.games.models import Collection, Game, ImportRun

GAMES = "/api/v1/games"
_hashes = itertools.count()

pytestmark = pytest.mark.django_db


def pgn_of(white: str, black: str, moves: str = "1. e4 e5 *") -> str:
    return f'[White "{white}"]\n[Black "{black}"]\n[Result "*"]\n\n{moves}\n'


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


@pytest.fixture
def alice_client(client: Client, alice: User) -> Client:
    client.force_login(alice)
    return client


def make_game(user: User, white: str = "Anna", black: str = "Ben", **fields: Any) -> Game:
    values = {
        "source": Game.Source.PGN,
        "pgn": pgn_of(white, black),
        "white": white,
        "black": black,
        "result": "*",
        "date": datetime.date(2024, 3, 5),
        "date_pgn": "2024.03.05",
        "time_class": "unknown",
        "ply_count": 2,
        "dedup_hash": f"{next(_hashes):064}",
        **fields,
    }
    return Game.objects.create(user=user, **values)


def test_a_game_has_its_headers_and_moves(alice_client: Client, alice: User) -> None:
    run = ImportRun.objects.create(user=alice, file_name="club.pgn", file_size=1)
    game = make_game(alice, import_run=run, eco="C20")

    response = alice_client.get(f"{GAMES}/{game.pk}")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["pgn"] == game.pgn
    assert (body["white"], body["black"], body["eco"]) == ("Anna", "Ben", "C20")
    assert body["import_run_id"] == run.pk


def test_downloads_one_game(alice_client: Client, alice: User) -> None:
    game = make_game(alice, white="Carlsen, Magnus")

    response = alice_client.get(f"{GAMES}/{game.pk}/pgn")

    assert response.status_code == HTTPStatus.OK
    assert response["Content-Type"] == "application/vnd.chess-pgn; charset=utf-8"
    assert response["Content-Disposition"] == (
        'attachment; filename="Carlsen, Magnus - Ben 2024.03.05.pgn"'
    )
    assert response.content.decode() == game.pgn


@pytest.mark.parametrize(
    ("fields", "file_name"),
    [
        ({"date_pgn": "????.??.??"}, "Anna - Ben.pgn"),  # no unknown date in the name
        ({"white": "", "black": ""}, "Unknown - Unknown 2024.03.05.pgn"),
        ({"white": "A/B"}, "A-B - Ben 2024.03.05.pgn"),  # no folders
    ],
)
def test_names_of_downloaded_files(
    alice_client: Client, alice: User, fields: dict[str, Any], file_name: str
) -> None:
    game = make_game(alice, **fields)

    response = alice_client.get(f"{GAMES}/{game.pk}/pgn")

    assert response["Content-Disposition"] == f'attachment; filename="{file_name}"'


def exported(client: Client, **params: Any) -> str:
    response = client.get(f"{GAMES}/export", params)
    assert response.status_code == HTTPStatus.OK
    assert response.streaming
    assert response["Content-Type"] == "application/vnd.chess-pgn; charset=utf-8"
    return response.getvalue().decode()


def test_exports_games_as_one_pgn_file(alice_client: Client, alice: User) -> None:
    older = make_game(alice, "Anna", "Ben", date=datetime.date(2020, 1, 1))
    newer = make_game(alice, "Cleo", "Dan", date=datetime.date(2024, 1, 1))

    text = exported(alice_client)

    assert text == newer.pgn + "\n" + older.pgn  # the list's order, a blank line between


def test_the_export_reads_back_as_the_same_games(alice_client: Client, alice: User) -> None:
    games = [
        make_game(alice, "Anna", "Ben", pgn=pgn_of("Anna", "Ben", "1. e4 {Best by test} e5 *")),
        make_game(alice, "Cleo", "Dan", pgn=pgn_of("Cleo", "Dan", "1. d4 (1. c4) d5 *")),
    ]

    read_back = list(read_pgn(exported(alice_client).encode().splitlines(keepends=True)))

    assert all(isinstance(game, PgnGame) for game in read_back)
    assert {game.pgn for game in read_back} == {game.pgn for game in games}


def test_exports_a_collection(alice_client: Client, alice: User) -> None:
    collected = make_game(alice)
    make_game(alice, "Cleo", "Dan")
    collection = Collection.objects.create(user=alice, name="Openings")
    collection.games.add(collected)

    assert exported(alice_client, collection=collection.pk) == collected.pgn


def test_exports_a_selection(alice_client: Client, alice: User) -> None:
    first, _, third = make_game(alice), make_game(alice), make_game(alice)

    text = exported(alice_client, ids=[first.pk, third.pk], sort="date")

    assert text == first.pgn + "\n" + third.pgn


def test_the_list_also_shows_a_selection(alice_client: Client, alice: User) -> None:
    first, _ = make_game(alice), make_game(alice)

    page = alice_client.get(GAMES, {"ids": [first.pk]}).json()

    assert [game["id"] for game in page["items"]] == [first.pk]


def test_an_empty_export_is_an_empty_file(alice_client: Client) -> None:
    assert exported(alice_client) == ""


# Isolation: users only ever see and export their own games.


def test_someone_elses_game_is_not_found(alice_client: Client) -> None:
    bobs = make_game(User.objects.create_user(username="bob"))

    for path in (f"{GAMES}/{bobs.pk}", f"{GAMES}/{bobs.pk}/pgn"):
        response = alice_client.get(path)
        assert response.status_code == HTTPStatus.NOT_FOUND, path
        assert bobs.pgn not in response.content.decode()


def test_the_export_leaves_out_someone_elses_games(alice_client: Client, alice: User) -> None:
    mine = make_game(alice)
    bobs = make_game(User.objects.create_user(username="bob"), "Bob", "Bert")

    assert exported(alice_client) == mine.pgn
    assert exported(alice_client, ids=[bobs.pk]) == ""


def test_games_require_login(client: Client, alice: User) -> None:
    game = make_game(alice)

    for path in (f"{GAMES}/{game.pk}", f"{GAMES}/{game.pk}/pgn", f"{GAMES}/export"):
        assert client.get(path).status_code == HTTPStatus.UNAUTHORIZED, path
