"""Drilling a repertoire: the card due longest, and whole lines."""

import chess
import pytest

from homerank.accounts.models import User
from homerank.repertoire import selectors
from homerank.repertoire.models import Repertoire, RepertoireMove
from homerank.repertoire.services import add_move, create_repertoire
from homerank.training import services as training
from homerank.training.models import ReviewCard

pytestmark = pytest.mark.django_db


@pytest.fixture
def white() -> Repertoire:
    alice = User.objects.create_user(username="alice")
    repertoire = create_repertoire(user=alice, name="Queen's Gambit", color="white")
    play(repertoire, "d4", "d5", "c4", "e6", "Nc3")
    play(repertoire, "d4", "d5", "c4", "c6", "Nf3")
    return repertoire


def play(repertoire: Repertoire, *sans: str) -> RepertoireMove:
    """Add the moves from the starting position; returns the last."""
    board = chess.Board()
    for san in sans:
        move = board.parse_san(san)
        added = add_move(repertoire, fen=board.fen(), move_uci=move.uci())
        board.push(move)
    return added


def learn(move: RepertoireMove) -> None:
    """Answer the move's card right, so it isn't due for a while."""
    training.review(ReviewCard.objects.get(repertoire_move=move), correct=True, elapsed_ms=900)


def test_the_card_due_longest_comes_first_after_its_last_move(white: Repertoire) -> None:
    first = selectors.next_due(white)
    learn(play(white, "d4"))

    second = selectors.next_due(white)

    assert first.step is not None
    assert (first.step.move_san, first.last_move_uci, first.due) == ("d4", "", 4)
    assert second.step is not None
    assert (second.step.move_san, second.last_move_uci, second.due) == ("c4", "d7d5", 3)
    assert second.step.fen == "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2"
    assert second.step.card_id is not None


def test_no_card_due(white: Repertoire) -> None:
    for sans in (["d4"], ["d4", "d5", "c4"], ["d4", "d5", "c4", "e6", "Nc3"]):
        learn(play(white, *sans))
    learn(play(white, "d4", "d5", "c4", "c6", "Nf3"))

    assert selectors.next_due(white) == selectors.DueDrill(step=None, last_move_uci="", due=0)


def test_a_line_runs_from_the_start_to_the_end(white: Repertoire) -> None:
    line = selectors.drill_line(white)

    assert [(s.move_san, s.card_id is not None) for s in line] == [
        ("d4", True),
        ("d5", False),
        ("c4", True),
        ("e6", False),  # 3. Nc3's card was made before 3. Nf3's, so it is due first
        ("Nc3", True),
    ]
    assert all(s.due for s in line if s.card_id is not None)


def test_a_line_follows_the_card_due_first(white: Repertoire) -> None:
    learn(play(white, "d4"))
    learn(play(white, "d4", "d5", "c4"))
    learn(play(white, "d4", "d5", "c4", "e6", "Nc3"))

    line = selectors.drill_line(white)

    assert [s.move_san for s in line] == ["d4", "d5", "c4", "c6", "Nf3"]
    assert [s.due for s in line if s.card_id is not None] == [False, False, True]


def test_a_line_through_a_chosen_move(white: Repertoire) -> None:
    c6 = play(white, "d4", "d5", "c4", "c6")

    line = selectors.drill_line(white, through=c6)

    assert [s.move_san for s in line] == ["d4", "d5", "c4", "c6", "Nf3"]


def test_other_own_moves_in_a_position_are_named(white: Repertoire) -> None:
    play(white, "Nf3")

    (first, *_) = selectors.drill_line(white)

    assert (first.move_san, first.other_moves) == ("d4", ["g1f3"])
    assert selectors.drill_line(white)[1].other_moves == []  # none for the opponent's moves


def test_a_line_doesnt_go_round_in_circles() -> None:
    alice = User.objects.create_user(username="alice")
    repertoire = create_repertoire(user=alice, name="Knights", color="white")
    play(repertoire, "Nf3", "Nf6", "Ng1", "Ng8")  # back to the starting position

    assert [s.move_san for s in selectors.drill_line(repertoire)] == ["Nf3", "Nf6", "Ng1", "Ng8"]


def test_an_empty_repertoire_has_no_line() -> None:
    alice = User.objects.create_user(username="alice")
    repertoire = create_repertoire(user=alice, name="Empty", color="black")

    assert selectors.drill_line(repertoire) == []


def test_after_the_chosen_move_a_line_takes_the_reply_whose_card_is_due_first(
    white: Repertoire,
) -> None:
    learn(play(white, "d4", "d5", "c4", "e6", "Nc3"))

    line = selectors.drill_line(white, through=play(white, "d4"))

    assert [s.move_san for s in line] == ["d4", "d5", "c4", "c6", "Nf3"]
