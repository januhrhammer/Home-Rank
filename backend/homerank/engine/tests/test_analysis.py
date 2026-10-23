import io

import chess.engine
import chess.pgn
import pytest

from homerank.engine.analysis import PV_LENGTH, analyse_game
from homerank.engine.uci import open_engine

pytestmark = pytest.mark.engine

DEPTH = 10  # quick, and deep enough for mate in one

WON = 97  # winning chances with a mate on the board
ABOUT_EQUAL_CP = 100
CLEARLY_BETTER = 75

SCHOLARS_MATE = "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0"


def game(pgn: str) -> chess.pgn.Game:
    parsed = chess.pgn.read_game(io.StringIO(pgn))
    assert parsed is not None
    return parsed


def test_every_position_is_analysed_from_whites_point_of_view(stockfish: str) -> None:
    with open_engine(stockfish) as engine:
        positions = list(analyse_game(engine, game(SCHOLARS_MATE), chess.engine.Limit(depth=DEPTH)))

    assert [p.ply for p in positions] == list(range(8))
    start = positions[0]
    assert start.depth >= DEPTH
    assert start.score_cp is not None
    assert abs(start.score_cp) < ABOUT_EQUAL_CP  # about equal
    assert 1 <= len(start.pv) <= PV_LENGTH
    assert start.best_move_uci == start.pv[0]
    # Before 4. Qxf7#: White mates in one, and the engine finds the move.
    before_mate = positions[6]
    assert (before_mate.score_mate, before_mate.best_move_uci) == (1, "h5f7")
    assert before_mate.win_percent > WON


def test_a_finished_position_needs_no_engine(stockfish: str) -> None:
    with open_engine(stockfish) as engine:
        *_, final = analyse_game(engine, game(SCHOLARS_MATE), chess.engine.Limit(depth=DEPTH))

    assert (final.depth, final.score_cp, final.score_mate) == (0, None, 0)
    assert (final.best_move_uci, final.pv) == ("", [])
    assert final.win_percent > WON  # Black is mated


def test_a_stalemate_is_a_draw(stockfish: str) -> None:
    stalemate = game('[SetUp "1"]\n[FEN "7k/5K2/8/6Q1/8/8/8/8 w - - 0 1"]\n\n1. Qg6 1/2-1/2')

    with open_engine(stockfish) as engine:
        *_, final = analyse_game(engine, stalemate, chess.engine.Limit(depth=DEPTH))

    assert (final.score_cp, final.score_mate, final.win_percent) == (0, None, 50)


def test_scores_stay_from_whites_point_of_view_when_black_is_to_move(stockfish: str) -> None:
    # White is a queen up and Black is to move: still good for White.
    queen_up = game('[SetUp "1"]\n[FEN "4k3/8/8/8/8/8/8/3QK3 b - - 0 1"]\n\n*')

    with open_engine(stockfish) as engine:
        (start,) = analyse_game(engine, queen_up, chess.engine.Limit(depth=DEPTH))

    # A shallow search's score varies from run to run; it is clearly good for White, though.
    assert start.win_percent > CLEARLY_BETTER
    assert (start.score_cp or 0) > 0 or (start.score_mate or 0) > 0
