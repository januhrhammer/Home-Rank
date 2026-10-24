"""Annotating a game through the API (ADR 0019): comments, variations and NAGs, never moves."""

import io
from http import HTTPStatus
from typing import Any

import pytest
from django.test import Client

from homerank.accounts.models import User
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.games.models import Game, GamePosition
from homerank.games.services import MAX_ANNOTATED_BYTES, new_game, store_games

pytestmark = pytest.mark.django_db

PGN = """[Event "Club championship"]
[White "alice64"]
[Black "Ben"]
[Date "2024.03.05"]
[Result "1-0"]

1. e4 { [%clk 0:03:00] } e5 { [%clk 0:02:59] } 2. Nf3 Nc6 3. Bb5 1-0
"""
ANNOTATED = "1. e4 { [%clk 0:03:00] } e5 2. Nf3 $1 ( 2. f4 { Sharper. } ) 2... Nc6 3. Bb5 1-0"


def first_game(pgn: str) -> PgnGame:
    item = next(iter(read_pgn(io.BytesIO(pgn.encode()))))
    assert isinstance(item, PgnGame)
    return item


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice", player_names=["alice64"])


@pytest.fixture
def game(alice: User) -> Game:
    store_games(alice, [new_game(alice, first_game(PGN))])
    return Game.objects.get(user=alice)


def put(client: Client, game_id: int, pgn: str) -> Any:
    return client.put(
        f"/api/v1/games/{game_id}/annotations", {"pgn": pgn}, content_type="application/json"
    )


def test_annotations_are_saved_and_nothing_else_changes(
    client: Client, alice: User, game: Game
) -> None:
    client.force_login(alice)
    positions = GamePosition.objects.filter(game=game).count()

    response = put(client, game.pk, ANNOTATED)

    assert response.status_code == HTTPStatus.OK
    pgn = response.json()["pgn"]
    assert "2. Nf3 $1 ( 2. f4 { Sharper. } )" in " ".join(pgn.split())
    assert '[Event "Club championship"]' in pgn
    game.refresh_from_db()
    assert game.pgn == pgn
    assert (game.white, game.result, game.user_color) == ("alice64", "1-0", "white")
    assert GamePosition.objects.filter(game=game).count() == positions
    again = new_game(alice, first_game(pgn))
    assert again.game.dedup_hash == game.dedup_hash  # still the same game


def test_the_moves_cant_change(client: Client, alice: User, game: Game) -> None:
    client.force_login(alice)

    response = put(client, game.pk, "1. e4 e5 2. f4 ( 2. Nf3 Nc6 3. Bb5 ) 1-0")

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["detail"].startswith("Annotations can't change the game's moves")
    game.refresh_from_db()
    assert game.pgn == PGN


def test_unreadable_and_too_large_games_are_refused(
    client: Client, alice: User, game: Game
) -> None:
    client.force_login(alice)

    unreadable = put(client, game.pk, "1. e4 e5 2. Ke3")
    too_large = put(client, game.pk, ANNOTATED.replace("Sharper.", "x" * MAX_ANNOTATED_BYTES))

    assert unreadable.status_code == HTTPStatus.BAD_REQUEST
    assert too_large.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    game.refresh_from_db()
    assert game.pgn == PGN


def test_someone_elses_game_is_not_found(client: Client, game: Game) -> None:
    client.force_login(User.objects.create_user(username="bob"))

    response = put(client, game.pk, ANNOTATED)

    assert response.status_code == HTTPStatus.NOT_FOUND
    game.refresh_from_db()
    assert game.pgn == PGN
