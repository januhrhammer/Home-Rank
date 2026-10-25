"""The explorer API: the moves from a position, and the games reaching it."""

import io
from http import HTTPStatus
from typing import Any
from urllib.parse import urlencode

import chess
import pytest
from django.test import Client

from homerank.accounts.models import User
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.games.services import new_game, store_games
from homerank.reference.models import ReferenceDatabase
from homerank.reference.tests.conftest import load_reference

pytestmark = pytest.mark.django_db

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
MY_GAME = '[White "alice64"]\n[Black "Ann"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 1-0\n'


@pytest.fixture
def alice() -> User:
    user = User.objects.create_user(username="alice", player_names=["alice64"])
    (item,) = read_pgn(io.BytesIO(MY_GAME.encode()))
    assert isinstance(item, PgnGame)
    store_games(user, [new_game(user, item)])
    return user


@pytest.fixture
def alice_client(client: Client, alice: User) -> Client:
    client.force_login(alice)
    return client


@pytest.fixture
def masters() -> ReferenceDatabase:
    return load_reference()


def get(client: Client, path: str, **query: object) -> Any:
    return client.get(f"/api/v1/explorer/{path}?{urlencode(query)}")


def test_my_explorer(alice_client: Client) -> None:
    body = get(alice_client, "my", fen=chess.STARTING_FEN).json()

    assert body["games"] == 1
    assert [(m["san"], m["white"]) for m in body["moves"]] == [("e4", 1)]


def test_the_explorer_names_the_position(alice_client: Client, masters: ReferenceDatabase) -> None:
    board = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6", "Bb5"):
        board.push_san(san)

    ruy = get(alice_client, "my", fen=board.fen()).json()
    start = get(alice_client, f"reference/{masters.pk}", fen=chess.STARTING_FEN).json()

    assert ruy["opening"] == {"eco": "C60", "name": "Ruy Lopez"}
    assert start["opening"] is None


def test_reference_explorer_with_and_without_filters(
    alice_client: Client, masters: ReferenceDatabase
) -> None:
    plain = get(alice_client, f"reference/{masters.pk}", fen=chess.STARTING_FEN).json()
    rated = get(
        alice_client, f"reference/{masters.pk}", fen=chess.STARTING_FEN, min_rating=2000
    ).json()

    assert sorted(m["san"] for m in plain["moves"]) == ["e4", "f3"]
    assert rated["moves"] == []  # nobody with both players rated 2000+
    assert rated["filtered"] is True


def test_searches_my_games_and_a_reference(
    alice_client: Client, masters: ReferenceDatabase
) -> None:
    mine = get(alice_client, "search/my", fen=AFTER_E4).json()
    theirs = get(alice_client, f"search/reference/{masters.pk}", fen=AFTER_E4).json()

    assert [(g["black"], g["ply"]) for g in mine["items"]] == [("Ann", 1)]
    assert mine["total"] == 1
    assert [(g["white"], g["ply"]) for g in theirs["items"]] == [("Morphy, Paul", 1)]
    assert theirs["too_common"] is False


def test_an_invalid_position_is_a_bad_request(alice_client: Client) -> None:
    response = get(alice_client, "my", fen="not a position")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "valid position" in response.json()["detail"]


def test_others_games_dont_show_in_my_explorer(client: Client, alice: User) -> None:
    client.force_login(User.objects.create_user(username="bob"))

    body = get(client, "my", fen=chess.STARTING_FEN).json()

    assert body == {"games": 0, "moves": [], "filtered": True, "opening": None}


def test_requires_login(client: Client) -> None:
    response = get(client, "my", fen=chess.STARTING_FEN)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
