"""A repertoire's lines (ADR 0020): named sets of its moves, each a path from the start."""

import io

import chess
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import Http404

from homerank.accounts.models import User
from homerank.games.services import NameTakenError
from homerank.repertoire import selectors, services
from homerank.repertoire.models import Repertoire, RepertoireLine, RepertoireMove
from homerank.repertoire.services import (
    InvalidLineOrderError,
    LastLineError,
    PositionNotInRepertoireError,
    TooManyLinesError,
    add_move,
    create_line,
    create_repertoire,
    delete_line,
    import_pgn,
    remove_move,
    rename_line,
    reorder_lines,
)
from homerank.training.models import ReviewCard

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


@pytest.fixture
def ruy(alice: User) -> Repertoire:
    return create_repertoire(user=alice, name="Ruy Lopez", color="white")


def play(repertoire: Repertoire, line: RepertoireLine, *sans: str) -> list[RepertoireMove]:
    board = chess.Board()
    moves = []
    for san in sans:
        move = board.parse_san(san)
        moves.append(add_move(repertoire, fen=board.fen(), move_uci=move.uci(), line=line))
        board.push(move)
    return moves


def line_sans(line: RepertoireLine) -> list[str]:
    return [m.move_san for m in line.moves.order_by("pk")]


BASE = ("e4", "e5", "Nf3", "Nc6", "Bb5")


def test_a_new_repertoire_starts_with_a_main_line(ruy: Repertoire) -> None:
    assert [line.name for line in selectors.lines(ruy)] == ["Main line"]


def test_lines_share_the_moves_they_have_in_common(ruy: Repertoire) -> None:
    main = selectors.lines(ruy).get()
    berlin = create_line(ruy, name="Berlin")
    play(ruy, main, *BASE, "a6", "Ba4")
    play(ruy, berlin, *BASE, "Nf6", "O-O")

    # 3.Bb5 is one move, with one card, in both lines.
    assert RepertoireMove.objects.filter(repertoire=ruy).count() == 9  # noqa: PLR2004
    assert ReviewCard.objects.filter(repertoire_move__repertoire=ruy).count() == 5  # noqa: PLR2004
    assert line_sans(main) == [*BASE, "a6", "Ba4"]
    assert line_sans(berlin) == [*BASE, "Nf6", "O-O"]


def test_a_move_needs_a_position_its_line_reaches(ruy: Repertoire) -> None:
    main = selectors.lines(ruy).get()
    berlin = create_line(ruy, name="Berlin")
    play(ruy, main, "e4", "e5")
    board = chess.Board()
    board.push_san("e4")
    board.push_san("e5")

    with pytest.raises(PositionNotInRepertoireError):
        add_move(ruy, fen=board.fen(), move_uci="g1f3", line=berlin)


def test_removing_a_move_from_a_line_keeps_it_for_the_other_lines(ruy: Repertoire) -> None:
    main = selectors.lines(ruy).get()
    berlin = create_line(ruy, name="Berlin")
    play(ruy, main, *BASE, "a6")
    bb5 = play(ruy, berlin, *BASE, "Nf6")[4]

    removed = remove_move(bb5, line=berlin)

    assert removed == 2  # noqa: PLR2004 - 3.Bb5 and 3…Nf6, which only it led to
    assert line_sans(berlin) == ["e4", "e5", "Nf3", "Nc6"]
    assert line_sans(main) == [*BASE, "a6"]
    # 3…Nf6 was in no other line: it is gone, with nothing left behind.
    assert not RepertoireMove.objects.filter(move_san="Nf6").exists()


def test_removing_a_move_from_every_line_deletes_it_and_its_card(ruy: Repertoire) -> None:
    main = selectors.lines(ruy).get()
    berlin = create_line(ruy, name="Berlin")
    play(ruy, main, *BASE)
    bb5 = play(ruy, berlin, *BASE)[4]

    removed = remove_move(bb5)

    assert removed == 1
    assert not RepertoireMove.objects.filter(pk=bb5.pk).exists()
    assert not ReviewCard.objects.filter(repertoire_move_id=bb5.pk).exists()
    assert line_sans(main) == line_sans(berlin) == ["e4", "e5", "Nf3", "Nc6"]


def test_line_names_are_unique_within_a_repertoire(alice: User, ruy: Repertoire) -> None:
    create_line(ruy, name="Berlin")
    other = create_line(ruy, name="Open")

    with pytest.raises(NameTakenError):
        create_line(ruy, name="Berlin")
    with pytest.raises(NameTakenError):
        rename_line(other, name="Berlin")
    sicilian = create_repertoire(user=alice, name="Sicilian", color="black")
    create_line(sicilian, name="Berlin")  # another repertoire's names don't count


def test_a_repertoire_has_a_limited_number_of_lines(
    ruy: Repertoire, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(services, "MAX_LINES", 2)
    create_line(ruy, name="Berlin")

    with pytest.raises(TooManyLinesError):
        create_line(ruy, name="Open")


def test_lines_keep_the_order_they_are_given(ruy: Repertoire) -> None:
    main = selectors.lines(ruy).get()
    berlin = create_line(ruy, name="Berlin")
    open_ = create_line(ruy, name="Open")
    assert [line.name for line in selectors.lines(ruy)] == ["Main line", "Berlin", "Open"]

    reorder_lines(ruy, line_ids=[open_.pk, main.pk, berlin.pk])

    assert [line.name for line in selectors.lines(ruy)] == ["Open", "Main line", "Berlin"]
    with pytest.raises(InvalidLineOrderError):
        reorder_lines(ruy, line_ids=[open_.pk, main.pk])


def test_deleting_a_line_deletes_the_moves_no_other_line_has(ruy: Repertoire) -> None:
    main = selectors.lines(ruy).get()
    berlin = create_line(ruy, name="Berlin")
    play(ruy, main, *BASE, "a6")
    play(ruy, berlin, *BASE, "Nf6", "O-O")

    removed = delete_line(berlin)

    assert removed == 2  # noqa: PLR2004 - 3…Nf6 4.O-O
    assert [m.move_san for m in selectors.moves(ruy)] == [*BASE, "a6"]
    with pytest.raises(LastLineError):
        delete_line(main)


def test_a_pgn_import_goes_into_the_chosen_line(ruy: Repertoire) -> None:
    main = selectors.lines(ruy).get()
    open_ = create_line(ruy, name="Open")
    play(ruy, main, *BASE, "a6")
    pgn = b"1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Nxe4 *\n"

    import_pgn(ruy, lines=io.BytesIO(pgn), into=open_)

    assert line_sans(open_) == [*BASE, "a6", "Ba4", "Nf6", "O-O", "Nxe4"]
    assert line_sans(main) == [*BASE, "a6"]


def test_conflicts_are_positions_where_lines_play_different_moves(ruy: Repertoire) -> None:
    main = selectors.lines(ruy).get()
    exchange = create_line(ruy, name="Exchange")
    play(ruy, main, *BASE, "a6", "Ba4")
    play(ruy, exchange, *BASE, "a6", "Bxc6")

    (conflict,) = selectors.conflicts(ruy)

    assert (
        conflict.fen
        == chess.Board("r1bqkbnr/1ppp1ppp/p1n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4").fen()
    )
    assert sorted((c.move_san, c.lines) for c in conflict.choices) == [
        ("Ba4", ["Main line"]),
        ("Bxc6", ["Exchange"]),
    ]


def test_alternatives_within_one_line_are_no_conflict(ruy: Repertoire) -> None:
    main = selectors.lines(ruy).get()
    play(ruy, main, *BASE, "a6", "Ba4")
    play(ruy, main, *BASE, "a6", "Bxc6")

    assert selectors.conflicts(ruy) == []


def test_users_see_only_their_own_lines(alice: User, ruy: Repertoire) -> None:
    bob = User.objects.create_user(username="bob")
    line = selectors.lines(ruy).get()

    assert selectors.line(user=alice, repertoire_id=ruy.pk, line_id=line.pk) == line
    with pytest.raises(Http404):
        selectors.line(user=bob, repertoire_id=ruy.pk, line_id=line.pk)


@pytest.mark.django_db(transaction=True)
def test_the_migration_gives_each_repertoire_a_main_line_with_all_its_moves() -> None:
    executor = MigrationExecutor(connection)
    before, after = [("repertoire", "0001_initial")], [("repertoire", "0002_lines")]
    try:
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        user = User.objects.create_user(username="carol")  # only the repertoire app went back
        repertoire = old.get_model("repertoire", "Repertoire").objects.create(
            user_id=user.pk, name="1. e4", color="white"
        )
        move = old.get_model("repertoire", "RepertoireMove")
        for zobrist, uci in ((1, "e2e4"), (2, "e7e5")):
            move.objects.create(
                repertoire_id=repertoire.pk,
                from_zobrist=zobrist,
                from_fen="-",
                move_uci=uci,
                move_san=uci,
                to_zobrist=zobrist + 1,
            )

        executor.loader.build_graph()
        executor.migrate(after)

        new = executor.loader.project_state(after).apps
        (line,) = new.get_model("repertoire", "RepertoireLine").objects.all()
        assert (line.repertoire_id, line.name) == (repertoire.pk, "Main line")
        assert line.moves.count() == 2  # noqa: PLR2004
    finally:
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
