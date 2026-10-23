from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction

from homerank.accounts.models import User
from homerank.repertoire.models import Repertoire, RepertoireMove
from homerank.training.models import ReviewCard, ReviewLog

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 23, tzinfo=UTC)
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
# Any numbers do for the hashes here; the services compute the real ones.
START_ZOBRIST = 1
AFTER_E4_ZOBRIST = 2


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


def make_move(repertoire: Repertoire, **fields: Any) -> RepertoireMove:
    values = {
        "from_zobrist": START_ZOBRIST,
        "from_fen": START_FEN,
        "move_uci": "e2e4",
        "move_san": "e4",
        "to_zobrist": AFTER_E4_ZOBRIST,
        **fields,
    }
    return RepertoireMove.objects.create(repertoire=repertoire, **values)


def test_a_users_repertoire_names_are_unique(alice: User) -> None:
    Repertoire.objects.create(user=alice, name="Open games", color="white")
    Repertoire.objects.create(
        user=User.objects.create_user(username="bob"), name="Open games", color="white"
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Repertoire.objects.create(user=alice, name="Open games", color="black")


def test_a_move_is_stored_once_per_position(alice: User) -> None:
    repertoire = Repertoire.objects.create(user=alice, name="1. e4", color="white")
    make_move(repertoire)
    make_move(repertoire, move_uci="d2d4", move_san="d4", to_zobrist=3)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_move(repertoire)  # the same move from the same position, however reached


def test_a_repertoire_card_needs_its_move(alice: User) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ReviewCard.objects.create(user=alice, card_type="repertoire", fsrs_state={}, due_at=NOW)


def test_deleting_a_repertoire_deletes_its_moves_cards_and_reviews(alice: User) -> None:
    repertoire = Repertoire.objects.create(user=alice, name="1. e4", color="white")
    move = make_move(repertoire)
    card = ReviewCard.objects.create(
        user=alice, card_type="repertoire", repertoire_move=move, fsrs_state={}, due_at=NOW
    )
    ReviewLog.objects.create(
        card=card, rating=3, correct=True, elapsed_ms=1500, card_state_before={}
    )

    repertoire.delete()

    for model in (RepertoireMove, ReviewCard, ReviewLog):
        assert not model.objects.exists()


def test_no_extra_indexes_on_the_foreign_keys() -> None:
    # The unique indexes serve lookups by user and by repertoire.
    def indexes(table: str) -> list[list[str]]:
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, table)
        return sorted(
            c["columns"]
            for c in constraints.values()
            if (c["index"] or c["unique"]) and not c["primary_key"]
        )

    assert indexes(Repertoire._meta.db_table) == [["user_id", "name"]]
    assert indexes(RepertoireMove._meta.db_table) == [["repertoire_id", "from_zobrist", "move_uci"]]
