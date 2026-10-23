from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import Client
from django.urls import reverse

from homerank.accounts.models import User
from homerank.games.models import Game
from homerank.training.models import Puzzle, PuzzleScan, ReviewCard, ReviewLog

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 23, tzinfo=UTC)


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


def make_game(user: User) -> Game:
    return Game.objects.create(
        user=user,
        source=Game.Source.PGN,
        pgn="1. f3 e5 2. g4 Qh4# 0-1\n",
        result="0-1",
        date_pgn="????.??.??",
        time_class="unknown",
        ply_count=4,
        dedup_hash="a" * 64,
    )


def make_puzzle(game: Game, **fields: Any) -> Puzzle:
    values = {
        "user": game.user,
        "ply": 3,
        "kind": "found",
        "fen": "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2",
        "last_move_uci": "g2g4",
        "solution": ["d8h4"],
        "themes": ["mateIn1"],
        "win_swing": 47.5,
        **fields,
    }
    return Puzzle.objects.create(game=game, **values)


def test_a_position_makes_one_puzzle(alice: User) -> None:
    game = make_game(alice)
    make_puzzle(game)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_puzzle(game)


def test_a_puzzle_card_needs_its_puzzle(alice: User) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ReviewCard.objects.create(user=alice, card_type="puzzle", fsrs_state={}, due_at=NOW)


def test_deleting_a_game_deletes_its_puzzles_cards_and_reviews(alice: User) -> None:
    game = make_game(alice)
    puzzle = make_puzzle(game)
    card = ReviewCard.objects.create(user=alice, puzzle=puzzle, fsrs_state={}, due_at=NOW)
    ReviewLog.objects.create(
        card=card, rating=3, correct=True, elapsed_ms=4200, card_state_before={}
    )
    PuzzleScan.objects.create(game=game, puzzles_found=1)

    game.delete()

    for model in (Puzzle, ReviewCard, ReviewLog, PuzzleScan):
        assert not model.objects.exists()


def test_no_extra_indexes_on_the_foreign_keys() -> None:
    # The composite indexes (unique ones included) serve lookups by user and game.
    def indexes(table: str) -> list[list[str]]:
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, table)
        return sorted(
            c["columns"]
            for c in constraints.values()
            if (c["index"] or c["unique"]) and not c["primary_key"]
        )

    assert indexes(Puzzle._meta.db_table) == [["game_id", "ply"], ["user_id", "created_at"]]
    assert indexes(ReviewCard._meta.db_table) == [["puzzle_id"], ["user_id", "due_at"]]


def test_staff_can_see_puzzles_but_not_add_them(admin_client: Client, alice: User) -> None:
    make_puzzle(make_game(alice))

    assert admin_client.get(reverse("admin:training_puzzle_changelist")).status_code == 200  # noqa: PLR2004
    assert admin_client.get(reverse("admin:training_puzzle_add")).status_code == 403  # noqa: PLR2004
