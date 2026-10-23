from collections.abc import Iterator
from typing import Any

import chess
import chess.engine
import pytest

from homerank.engine.tactics import (
    MAX_PLIES,
    Candidate,
    PuzzleKind,
    find_candidates,
    solve,
    themes,
)
from homerank.engine.uci import open_engine

FOOLS_MATE_BEFORE_QH4 = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2")
HANGING_QUEEN = chess.Board("4k3/8/8/3q4/8/8/8/3QK3 w - - 0 1")

# ---------------------------------------------------------------- candidates

MOVES = ["e2e4", "e7e5", "d1h5", "b8c6", "h5f7"]  # only the length and equality matter
BEST = ["e2e4", "e7e5", "d1h5", "g8f6", "h5f7"]


def test_an_opponent_blunder_the_user_punished_is_found() -> None:
    # White's chances: Black's 2... Nc6 (ply 3) gives White a won position.
    wins = [50.0, 52.0, 50.0, 51.0, 90.0, 92.0]

    candidates = find_candidates(wins, MOVES, BEST, user_white=True)

    assert candidates == [Candidate(4, PuzzleKind.FOUND, 39.0)]


def test_an_opponent_blunder_the_user_missed() -> None:
    wins = [50.0, 52.0, 50.0, 51.0, 90.0, 60.0]
    best = [*BEST[:4], "f1c4"]  # the user didn't play the engine's move

    candidates = find_candidates(wins, MOVES, best, user_white=True)

    assert candidates == [Candidate(4, PuzzleKind.OPPONENT_BLUNDER, 39.0)]


def test_a_chance_the_user_threw_away_is_missed() -> None:
    wins = [70.0, 70.0, 70.0, 70.0, 75.0, 40.0]  # 3. h5f7 (ply 4) drops from 75 to 40

    candidates = find_candidates(wins, MOVES, BEST, user_white=True)

    assert candidates == [Candidate(4, PuzzleKind.MISSED, 35.0)]


def test_positions_without_a_clear_advantage_are_no_puzzles() -> None:
    wins = [50.0, 50.0, 60.0, 60.0, 60.0, 30.0]  # a big drop, but from only 60 %

    assert find_candidates(wins, MOVES, BEST, user_white=True) == []


def test_only_the_users_own_turns_count() -> None:
    # The same swings seen by a user playing Black: White's turns are not theirs.
    wins = [50.0, 52.0, 50.0, 51.0, 90.0, 92.0]

    assert find_candidates(wins, MOVES, BEST, user_white=False) == []


def test_the_opponents_turns_are_no_puzzles() -> None:
    # White's 3rd move (ply 4) drops from 20 to 60 % for White: a chance missed by White,
    # which is the opponent of this user, who plays Black.
    wins = [20.0, 20.0, 20.0, 20.0, 20.0, 60.0]

    assert find_candidates(wins, MOVES, BEST, user_white=False) == []
    assert find_candidates(wins, MOVES, BEST, user_white=True) == []  # 20 % isn't clear


def test_black_users_see_the_chances_from_their_side() -> None:
    # 2... (ply 3) is Black's move, at 85 % for Black, and loses 45 points.
    wins = [20.0, 20.0, 20.0, 15.0, 60.0, 60.0]

    candidates = find_candidates(wins, MOVES, BEST, user_white=False)

    assert candidates == [Candidate(3, PuzzleKind.MISSED, 45.0)]


# ---------------------------------------------------------------- themes


def test_a_mating_solution_has_the_theme_mate_in_n() -> None:
    assert themes(FOOLS_MATE_BEFORE_QH4, ["d8h4"]) == ["mate", "mateIn1"]


def test_winning_material_has_the_theme_material() -> None:
    assert themes(HANGING_QUEEN, ["d1d5"]) == ["material"]


def test_a_quiet_solution_has_no_theme() -> None:
    assert themes(chess.Board(), ["e2e4"]) == []


# ---------------------------------------------------------------- solving, with a scripted engine


def info(move: str, cp: int | None = None, mate: int | None = None, reply: str = "") -> Any:
    """An engine answer for the side to move: its score and line."""
    score = chess.engine.Mate(mate) if mate is not None else chess.engine.Cp(cp or 0)
    pv = [chess.Move.from_uci(move)] + ([chess.Move.from_uci(reply)] if reply else [])
    return {"score": score, "pv": pv}


class ScriptedEngine:
    """Answers analyse() with the given lists of (best, second best), one after another."""

    def __init__(self, answers: list[list[Any]]) -> None:
        self.answers: Iterator[list[Any]] = iter(answers)

    def analyse(self, board: chess.Board, limit: Any, multipv: int) -> list[Any]:
        return [
            {**answer, "score": chess.engine.PovScore(answer["score"], board.turn)}
            for answer in next(self.answers)
        ]


def solve_scripted(board: chess.Board, answers: list[list[Any]]) -> list[str]:
    return solve(ScriptedEngine(answers), board, chess.engine.Limit(depth=1))  # type: ignore[arg-type]


def test_the_solution_continues_while_the_best_move_stays_unique() -> None:
    answers = [
        [info("e2e4", 400, reply="e7e5"), info("d2d4", 0)],  # unique: 400 vs 0
        [info("g1f3", 500, reply="b8c6"), info("b1c3", 30)],  # unique again
        [info("f1c4", 600), info("f1b5", 590)],  # two good moves: the puzzle ends before
    ]

    assert solve_scripted(chess.Board(), answers) == ["e2e4", "e7e5", "g1f3"]


def test_no_unique_first_move_is_no_puzzle() -> None:
    answers = [[info("e2e4", 400), info("d2d4", 390)]]

    assert solve_scripted(chess.Board(), answers) == []


def test_a_mate_isnt_unique_if_the_second_move_wins_anyway() -> None:
    answers = [[info("e2e4", mate=3), info("d2d4", 1500)]]

    assert solve_scripted(chess.Board(), answers) == []


def test_a_mate_is_unique_if_the_second_move_doesnt_mate() -> None:
    answers = [[info("e2e4", mate=3, reply="e7e5"), info("d2d4", 300)]]
    answers.append([info("g1f3", mate=2), info("b1c3", mate=4)])  # two mates: stop

    assert solve_scripted(chess.Board(), answers) == ["e2e4"]


def test_solutions_have_a_limit() -> None:
    moves = ["g1f3", "g8f6", "f3g1", "f6g8"] * 3
    answers = [[info(moves[i], 500, reply=moves[i + 1]), info("a2a3", 0)] for i in range(0, 12, 2)]

    solution = solve_scripted(chess.Board(), answers)

    assert len(solution) == MAX_PLIES
    assert len(solution) % 2 == 1  # it ends with the solver's move


# ---------------------------------------------------------------- solving, with Stockfish

DEPTH = 14


@pytest.mark.engine
def test_stockfish_finds_a_unique_mate_in_one(stockfish: str) -> None:
    with open_engine(stockfish) as engine:
        solution = solve(engine, FOOLS_MATE_BEFORE_QH4, chess.engine.Limit(depth=DEPTH))

    assert solution == ["d8h4"]


@pytest.mark.engine
def test_stockfish_finds_a_hanging_queen(stockfish: str) -> None:
    with open_engine(stockfish) as engine:
        solution = solve(engine, HANGING_QUEEN, chess.engine.Limit(depth=DEPTH))

    assert solution[0] == "d1d5"


@pytest.mark.engine
def test_a_position_where_many_moves_win_is_no_puzzle(stockfish: str) -> None:
    queen_and_rook = chess.Board("4k3/8/8/8/8/8/8/QR2K3 w - - 0 1")  # many moves mate soon

    with open_engine(stockfish) as engine:
        assert solve(engine, queen_and_rook, chess.engine.Limit(depth=DEPTH)) == []
