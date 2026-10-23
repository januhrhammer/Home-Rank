"""Building repertoires: moves, transpositions, cards, PGN import, and who may see what."""

import io

import chess
import pytest
from django.http import Http404

from homerank.accounts.models import User
from homerank.games.services import NameTakenError
from homerank.repertoire import selectors, services
from homerank.repertoire.models import Repertoire, RepertoireMove
from homerank.repertoire.services import (
    IllegalMoveError,
    InvalidPositionError,
    PgnTooLargeError,
    PositionNotInRepertoireError,
    TooManyMovesError,
    TooManyRepertoiresError,
    add_move,
    create_repertoire,
    import_pgn,
    remove_move,
    rename_repertoire,
    set_comment,
)
from homerank.training import selectors as training_selectors
from homerank.training import services as training
from homerank.training.models import ReviewCard

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


@pytest.fixture
def white(alice: User) -> Repertoire:
    return create_repertoire(user=alice, name="Queen's Gambit", color="white")


def fen_after(*sans: str) -> str:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board.fen()


def play(repertoire: Repertoire, *sans: str) -> list[RepertoireMove]:
    """Add the moves one after the other from the starting position."""
    board = chess.Board()
    moves = []
    for san in sans:
        move = board.parse_san(san)
        moves.append(add_move(repertoire, fen=board.fen(), move_uci=move.uci()))
        board.push(move)
    return moves


def sans(repertoire: Repertoire) -> list[str]:
    return [m.move_san for m in selectors.moves(repertoire)]


# ---------------------------------------------------------------- repertoires


def test_names_are_unique_per_user(alice: User, white: Repertoire) -> None:
    other = create_repertoire(user=alice, name="Sicilian", color="black")

    with pytest.raises(NameTakenError):
        create_repertoire(user=alice, name="Queen's Gambit", color="black")
    with pytest.raises(NameTakenError):
        rename_repertoire(other, name="Queen's Gambit")


def test_a_user_has_a_limited_number_of_repertoires(alice: User) -> None:
    for number in range(services.MAX_REPERTOIRES):
        create_repertoire(user=alice, name=f"r{number}", color="white")

    with pytest.raises(TooManyRepertoiresError):
        create_repertoire(user=alice, name="one more", color="white")


# ---------------------------------------------------------------- moves


def test_moves_are_added_from_the_start(white: Repertoire) -> None:
    d4, d5 = play(white, "d4", "d5")

    assert (d4.move_san, d4.from_fen) == ("d4", chess.STARTING_FEN)
    assert d5.from_zobrist == d4.to_zobrist
    assert sans(white) == ["d4", "d5"]


def test_adding_a_move_twice_keeps_one(white: Repertoire) -> None:
    (first,) = play(white, "d4")
    (again,) = play(white, "d4")

    assert again == first
    assert RepertoireMove.objects.count() == 1


def test_a_transposition_is_one_position_with_one_set_of_moves(white: Repertoire) -> None:
    play(white, "d4", "Nf6", "c4", "e6", "Nc3")
    *_, nc3 = play(white, "c4", "e6", "d4", "Nf6", "Nc3")  # the same position by another order

    assert sans(white) == ["d4", "Nf6", "c4", "e6", "Nc3", "c4", "e6", "d4", "Nf6"]
    assert nc3.move_san == "Nc3"  # found, not added again
    assert ReviewCard.objects.filter(repertoire_move=nc3).count() == 1


def test_a_move_needs_a_position_the_repertoire_reaches(white: Repertoire) -> None:
    play(white, "d4")

    with pytest.raises(PositionNotInRepertoireError):
        add_move(white, fen=fen_after("e4"), move_uci="e7e5")


@pytest.mark.parametrize("fen", ["not a fen", "8/8/8/8/8/8/8/8 w - - 0 1"])
def test_a_move_needs_a_valid_position(white: Repertoire, fen: str) -> None:
    with pytest.raises(InvalidPositionError):
        add_move(white, fen=fen, move_uci="e2e4")


@pytest.mark.parametrize("move_uci", ["e2e5", "nonsense"])
def test_a_move_must_be_legal(white: Repertoire, move_uci: str) -> None:
    with pytest.raises(IllegalMoveError):
        add_move(white, fen=chess.STARTING_FEN, move_uci=move_uci)


def test_a_repertoire_has_a_limited_number_of_moves(
    white: Repertoire, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(services, "MAX_MOVES", 2)
    play(white, "d4", "d5")

    with pytest.raises(TooManyMovesError):
        play(white, "d4", "d5", "c4")


def test_the_users_own_moves_get_cards(alice: User, white: Repertoire) -> None:
    black = create_repertoire(user=alice, name="Slav", color="black")
    d4, _, c4 = play(white, "d4", "d5", "c4")
    _, b_d5, _, b_c6 = play(black, "d4", "d5", "c4", "c6")

    cards = ReviewCard.objects.filter(user=alice, card_type="repertoire")
    assert {c.repertoire_move for c in cards} == {d4, c4, b_d5, b_c6}
    assert all(c.due_at is not None for c in cards)


def test_removing_a_move_removes_what_only_it_led_to(white: Repertoire) -> None:
    d4, *_ = play(white, "d4", "d5", "c4", "e6")
    play(white, "Nf3", "d5", "d4")  # 2. d4 leads where only this line goes (1. d4 d5 2. Nf3)
    (nf3,) = play(white, "Nf3")

    removed = remove_move(nf3)

    assert removed == 3  # noqa: PLR2004
    assert sans(white) == ["d4", "d5", "c4", "e6"]
    assert ReviewCard.objects.filter(repertoire_move__repertoire=white).count() == 2  # noqa: PLR2004
    assert d4 in selectors.moves(white)


def test_removing_a_move_keeps_a_position_reached_another_way(white: Repertoire) -> None:
    play(white, "d4", "Nf6", "c4", "e6", "Nc3")
    c4, *_ = play(white, "c4", "e6", "d4", "Nf6")

    remove_move(c4)

    assert sans(white) == ["d4", "Nf6", "c4", "e6", "Nc3"]


def test_a_comment_is_stored_without_surrounding_space(white: Repertoire) -> None:
    (d4,) = play(white, "d4")

    set_comment(d4, comment="  Queen's pawn \n")

    d4.refresh_from_db()
    assert d4.comment == "Queen's pawn"


# ---------------------------------------------------------------- PGN import


def test_a_pgn_import_adds_every_line_and_comment(white: Repertoire) -> None:
    play(white, "d4")
    text = (
        "1. d4 { old } d5 { solid } 2. c4 (2. Nf3 Nf6) e6 *\n\n"
        '[FEN "8/8/8/8/8/8/k7/K6R w - - 0 1"]\n[SetUp "1"]\n\n1. Rh2+ *\n\n'
        "1. d4 Nf6 2. c4 *\n"
    )

    result = import_pgn(white, lines=io.BytesIO(text.encode()))

    assert result == services.PgnImport(moves_added=7, games_read=2, games_skipped=1)
    assert sans(white) == ["d4", "d5", "c4", "Nf3", "e6", "Nf6", "Nf6", "c4"]
    moves = list(selectors.moves(white))
    assert moves[0].comment == ""  # moves already there stay as they were
    assert moves[1].comment == "solid"
    assert ReviewCard.objects.filter(repertoire_move__repertoire=white).count() == 4  # noqa: PLR2004


def test_a_pgn_import_over_the_limit_adds_nothing(
    white: Repertoire, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(services, "MAX_MOVES", 3)

    with pytest.raises(TooManyMovesError):
        import_pgn(white, lines=io.BytesIO(b"1. d4 d5 2. c4 e6 *"))

    assert not RepertoireMove.objects.exists()


def test_a_pgn_file_over_the_size_limit_is_refused(
    white: Repertoire, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(services, "MAX_PGN_BYTES", 20)

    with pytest.raises(PgnTooLargeError):
        import_pgn(white, lines=io.BytesIO(b"1. d4 d5 2. c4 e6\n3. Nc3 Nf6 *\n"))

    assert not RepertoireMove.objects.exists()


# ---------------------------------------------------------------- isolation


def test_users_see_only_their_own_repertoires_and_moves(alice: User, white: Repertoire) -> None:
    bob = User.objects.create_user(username="bob")
    create_repertoire(user=bob, name="Bob's", color="white")
    (d4,) = play(white, "d4")

    assert [r.name for r in selectors.repertoires(user=alice)] == ["Queen's Gambit"]
    assert selectors.repertoires(user=alice)[0].move_count == 1  # type: ignore[attr-defined]
    with pytest.raises(Http404):
        selectors.repertoire(user=bob, repertoire_id=white.pk)
    with pytest.raises(Http404):
        selectors.move(user=bob, repertoire_id=white.pk, move_id=d4.pk)


def test_a_move_belongs_to_its_repertoire(alice: User, white: Repertoire) -> None:
    other = create_repertoire(user=alice, name="London", color="white")
    (d4,) = play(white, "d4")

    with pytest.raises(Http404):
        selectors.move(user=alice, repertoire_id=other.pk, move_id=d4.pk)


# ---------------------------------------------------------------- reviews


def test_a_repertoire_move_right_first_time_is_good_else_again(white: Repertoire) -> None:
    (d4,) = play(white, "d4")
    card = ReviewCard.objects.get(repertoire_move=d4)

    assert training.review(card, correct=True, elapsed_ms=60_000).rating == 3  # noqa: PLR2004
    assert training.review(card, correct=False, elapsed_ms=900).rating == 1


def test_puzzle_statistics_leave_repertoire_cards_out(alice: User, white: Repertoire) -> None:
    (d4,) = play(white, "d4")
    training.review(ReviewCard.objects.get(repertoire_move=d4), correct=True, elapsed_ms=900)

    stats = training_selectors.stats(user=alice)

    assert (stats.due_now, stats.due_today, stats.reviewed_today, stats.weeks) == (0, 0, 0, [])
