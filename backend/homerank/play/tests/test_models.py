from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from homerank.accounts.models import User
from homerank.games.models import Game
from homerank.play.models import BotGame

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 23, tzinfo=UTC)
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


def make_game(user: User, **fields: Any) -> BotGame:
    values = {
        "start_fen": START_FEN,
        "user_color": "white",
        "opponent": "maia",
        "opponent_elo": 1500,
        **fields,
    }
    return BotGame.objects.create(user=user, **values)


def rejected(**fields: Any) -> None:
    """The database refuses a game with these fields."""
    user = User.objects.get(username="alice")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_game(user, **fields)


def test_a_new_game_is_untimed_and_being_played(alice: User) -> None:
    game = make_game(alice)

    assert (game.moves, game.move_ms, game.status, game.result) == ([], [], "playing", "")
    assert game.clock_base_ms is None


def test_every_move_has_its_time(alice: User) -> None:
    make_game(alice, moves=["e2e4", "c7c5"], move_ms=[1200, 3])

    rejected(moves=["e2e4", "c7c5"], move_ms=[1200])
    rejected(moves=[], move_ms=[5])


def test_a_clock_has_a_base_time_and_an_increment(alice: User) -> None:
    make_game(alice, clock_base_ms=600_000, clock_increment_ms=5_000)
    make_game(alice, clock_base_ms=180_000, clock_increment_ms=0)

    rejected(clock_base_ms=600_000)
    rejected(clock_increment_ms=5_000)
    rejected(clock_base_ms=0, clock_increment_ms=5_000)


def test_a_finished_game_has_its_result_how_it_ended_and_when(alice: User) -> None:
    make_game(alice, status="finished", result="1-0", termination="checkmate", finished_at=NOW)

    rejected(status="finished", result="1-0", termination="checkmate")  # no finished_at
    rejected(status="finished", termination="resignation", finished_at=NOW)  # no result
    rejected(status="finished", result="0-1", finished_at=NOW)  # no termination


def test_a_game_being_played_has_no_result(alice: User) -> None:
    rejected(result="1-0")
    rejected(termination="timeout")
    rejected(finished_at=NOW)


def test_deleting_the_saved_game_keeps_the_bot_game(alice: User) -> None:
    saved = Game.objects.create(
        user=alice,
        source=Game.Source.PGN,
        pgn="1. e4 *",
        white="alice",
        black="Maia 1500",
        result="*",
        time_class="unknown",
        ply_count=1,
        dedup_hash="0" * 64,
    )
    game = make_game(alice, saved_game=saved)

    saved.delete()

    game.refresh_from_db()
    assert game.saved_game is None
