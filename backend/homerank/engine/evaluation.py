"""What engine scores mean for players: winning chances, mistakes and accuracy.

The formulas are Lichess's, so the numbers match what players know from there:
https://lichess.org/page/accuracy. Scores are in centipawns (cp) or moves to mate, as engines
report them; everything here is from White's point of view unless a function says otherwise.
"""

import math
from collections.abc import Sequence
from enum import StrEnum
from statistics import pstdev

# Lichess caps scores at ten pawns: beyond that, the chances hardly change.
MAX_CP = 1000


class MissingScoreError(ValueError):
    def __init__(self) -> None:
        super().__init__("a score needs cp or mate")


def win_percent(cp: int | None, mate: int | None, *, white_to_move: bool) -> float:
    """White's winning chances, 0 to 100, from an engine score from White's point of view.

    A mate counts as the largest score. mate=0 means the side to move is checkmated, so
    `white_to_move` says who won; elsewhere it doesn't matter.
    """
    if mate is not None:
        white_wins = mate > 0 or (mate == 0 and not white_to_move)
        cp = MAX_CP if white_wins else -MAX_CP
    if cp is None:
        raise MissingScoreError
    capped = max(-MAX_CP, min(MAX_CP, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * capped)) - 1)


class MoveClass(StrEnum):
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"


# The default thresholds: how many percentage points of winning chances a move may lose.
DEFAULT_THRESHOLDS = (10.0, 20.0, 30.0)  # inaccuracy, mistake, blunder


def classify(
    before: float,
    after: float,
    *,
    white_moved: bool,
    thresholds: tuple[float, float, float] = DEFAULT_THRESHOLDS,
) -> MoveClass:
    """How bad a move was, by the winning chances (White's view) before and after it."""
    loss = (before - after) if white_moved else (after - before)
    inaccuracy, mistake, blunder = thresholds
    if loss >= blunder:
        return MoveClass.BLUNDER
    if loss >= mistake:
        return MoveClass.MISTAKE
    if loss >= inaccuracy:
        return MoveClass.INACCURACY
    return MoveClass.GOOD


def move_accuracy(before: float, after: float) -> float:
    """A move's accuracy, 0 to 100, by the mover's winning chances before and after it."""
    if after >= before:
        return 100.0
    raw = 103.1668100711649 * math.exp(-0.04354415386753951 * (before - after)) - 3.166924740191411
    return max(0.0, min(100.0, raw + 1))  # +1: Lichess's allowance for imperfect analysis


def game_accuracy(wins: Sequence[float], *, white_first: bool = True) -> tuple[float, float] | None:
    """White's and Black's accuracy in a game, from White's winning chances in every position
    of the main line, the starting position first. None for a game without moves.

    Like Lichess: each move's accuracy is weighted by how much the chances swing around it (a
    quiet phase counts less), and the weighted mean is averaged with the harmonic mean, which
    punishes single bad moves.
    """
    moves = len(wins) - 1
    if moves < 1:
        return None
    size = max(2, min(8, moves // 10))
    # One window per move: the first few repeat the opening window, as on Lichess.
    windows = [wins[:size]] * (size - 2) + [wins[i : i + size] for i in range(len(wins) - size + 1)]
    weights = [max(0.5, min(12.0, pstdev(window))) for window in windows]

    per_side: dict[bool, list[tuple[float, float]]] = {True: [], False: []}
    for i in range(moves):
        white_moved = (i % 2 == 0) == white_first
        before, after = wins[i], wins[i + 1]
        if not white_moved:
            before, after = 100 - before, 100 - after
        per_side[white_moved].append((move_accuracy(before, after), weights[i]))

    def side_accuracy(moves_of_side: list[tuple[float, float]]) -> float:
        if not moves_of_side:
            return 100.0
        weighted = sum(a * w for a, w in moves_of_side) / sum(w for _, w in moves_of_side)
        harmonic = len(moves_of_side) / sum(1 / max(a, 0.001) for a, _ in moves_of_side)
        return (weighted + harmonic) / 2

    return side_accuracy(per_side[True]), side_accuracy(per_side[False])
