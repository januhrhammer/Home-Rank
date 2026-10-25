"""Novelty search: tries that give up a little evaluation but are hard to refute (ADR 0022).

From a start position, for one side ("us"), an expectimax search against a model of the
opponent:

- At our moves, the engine's best moves whose evaluation stays within a risk budget; a position
  is worth the best of them.
- At the opponent's moves, the model's likeliest moves (together most of its probability); a
  position is worth their probability-weighted mean.
- At the end of the search, the engine's evaluation as our winning chance.

A try is one of our moves that is not the engine's best but is worth more against the model.
The search deepens step by step and reports the tries after each step, so that it can be
stopped at any time with a useful result. It needs no Django: the app gives it evaluators
(Stockfish) and an opponent model (Maia) and stores what it reports.
"""

import math
import queue
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Protocol

import chess
import chess.engine

from homerank.engine.evaluation import MAX_CP
from homerank.engine.maia import Maia

# Mate as centipawns: beyond any real evaluation.
MATE_CP = 10 * MAX_CP


@dataclass(frozen=True)
class Line:
    move: chess.Move
    cp: int  # for the side to move


class Evaluator(Protocol):
    """The engine: its best moves in a position, with their evaluations."""

    def lines(self, board: chess.Board, *, depth: int, count: int) -> list[Line]:
        """Up to `count` best moves, best first, evaluated for the side to move (mates as
        ±MATE_CP)."""
        ...


class OpponentModel(Protocol):
    """How likely a player of a rating plays each legal move."""

    def probabilities(self, board: chess.Board, *, elo: int) -> dict[chess.Move, float]: ...


@dataclass(frozen=True)
class Settings:
    us: chess.Color
    elo: int  # the opponent's rating, as the model takes it
    budget_cp: int = 150  # how far below 0 our moves may go
    depth: int = 14  # of the engine's searches during the search
    verify_depth: int = 24  # of the check of the tries found
    candidates: int = 6  # our moves looked at for our first two moves
    deeper_candidates: int = 4  # our moves looked at further on
    reply_mass: float = 0.90  # the opponent's moves covering this much of the model's probability
    max_replies: int = 3  # but at most this many
    good_enough: float = 0.05  # a reply this close to the best in winning chance keeps the edge
    shown_tries: int = 10  # tries checked at verify_depth and reported per step


@dataclass(frozen=True)
class RefutationStep:
    """A move of the refutation: the opponent's with how likely they find a good one, ours
    (the engine's answers in between) without."""

    san: str
    uci: str
    # For the opponent's moves: the probability that the model plays this move or one nearly
    # as good. None for ours.
    found: float | None


@dataclass(frozen=True)
class Try:
    line: list[str]  # the moves (UCI) from the start to the position of the try
    uci: str
    san: str
    cp: int  # for us, at verify_depth
    practical: float  # our expected score against the model, 0 to 1
    best_san: str  # the engine's move in that position
    best_practical: float
    reach: float  # how often the opponent's likely moves lead to the position
    refutation: list[RefutationStep] = field(default_factory=list)

    @property
    def gain(self) -> float:
        return self.practical - self.best_practical

    @property
    def refuted(self) -> float:
        """How likely the opponent finds every move of the refutation."""
        return math.prod(step.found for step in self.refutation if step.found is not None)


@dataclass(frozen=True)
class _Found:
    """A move of ours worth more than the engine's best one, before it is checked."""

    reach: float
    line: list[str]
    move: chess.Move
    value: float
    best_move: chess.Move
    best_value: float

    @property
    def rank(self) -> float:
        # Gain, counting fully once the line reaches the position at least one time in five.
        return (self.value - self.best_value) * min(1.0, self.reach * 5)


class Stopped(Exception):  # noqa: N818 - a signal, not an error
    """The search was asked to stop (time limit or cancelled)."""


def winning_chance(cp: int) -> float:
    """The chance to win, 0 to 1, for the side whose evaluation `cp` is (Lichess's formula)."""
    capped = max(-MAX_CP, min(MAX_CP, cp))
    return 1 / (1 + math.exp(-0.00368208 * capped))


class EnginePool:
    """Evaluators shared by the search's threads: each call borrows a free one."""

    def __init__(self, evaluators: list[Evaluator]) -> None:
        self._free: queue.Queue[Evaluator] = queue.Queue()
        for evaluator in evaluators:
            self._free.put(evaluator)
        self.size = len(evaluators)

    @contextmanager
    def borrow(self) -> Iterator[Evaluator]:
        evaluator = self._free.get()
        try:
            yield evaluator
        finally:
            self._free.put(evaluator)


class Search:
    """One search from one start position. `should_stop` is asked at every position; once it
    says yes, the step under way ends, and the tries of the last finished step stand."""

    def __init__(
        self,
        start: chess.Board,
        settings: Settings,
        pool: EnginePool,
        model: OpponentModel,
        should_stop: Callable[[], bool] = lambda: False,
    ) -> None:
        self.start = start
        self.settings = settings
        self.pool = pool
        self.model = model
        self.should_stop = should_stop
        # Results by position: positions recur in every step, and within a step.
        self._lines: dict[tuple[str, int, int], list[Line]] = {}
        self._replies: dict[str, dict[chess.Move, float]] = {}
        self._found: list[_Found] = []
        self._widen = 1  # how many times the usual candidates at our first two moves
        self._lock = threading.Lock()

    def steps(self) -> Iterator[tuple[int, list[Try]]]:
        """Deeper and deeper: two of our moves, three, four, then four with twice the
        candidates at our first two moves. Yields the number of our moves and the tries after
        each finished step; ends early when stopped."""
        for own_moves, widen in ((2, 1), (3, 1), (4, 1), (4, 2)):
            try:
                tries = self.run(own_moves, widen=widen)
            except Stopped:
                return
            yield own_moves, tries

    def run(self, own_moves: int, *, widen: int = 1) -> list[Try]:
        """One step: the tries found looking `own_moves` of our moves ahead, the best first."""
        self._found = []
        self._widen = widen
        start = self.start.copy()
        if start.turn == self.settings.us:
            # Our move first: each candidate's subtree in a thread of its own, so that all the
            # pool's engines work at once.
            candidates = self._candidates(start, first=True)
            with ThreadPoolExecutor(max(1, self.pool.size)) as threads:
                values = list(
                    threads.map(
                        lambda c: self._after(start, c.move, own_moves - 1, 1.0), candidates
                    )
                )
            self._note(start, candidates, values, 1.0)
        else:
            self._value(start, own_moves, 1.0)
        return self._checked()

    # ------------------------------------------------------------- the expectimax

    def _value(self, board: chess.Board, own_left: int, reach: float) -> float:
        """Our expected score from this position against the model."""
        if self.should_stop():
            raise Stopped
        if board.is_game_over(claim_draw=True):
            return self._result(board)
        if board.turn != self.settings.us:
            total = weight = 0.0
            for move, probability in self._likely_replies(board):
                total += probability * self._after(board, move, own_left, reach * probability)
                weight += probability
            return total / weight if weight else 0.5
        candidates = self._candidates(board, first=self._ply(board) < 2) if own_left else []  # noqa: PLR2004
        if not candidates:
            return self._static(board)
        values = [self._after(board, c.move, own_left - 1, reach) for c in candidates]
        self._note(board, candidates, values, reach)
        return max(values)

    def _after(self, board: chess.Board, move: chess.Move, own_left: int, reach: float) -> float:
        after = board.copy()  # with the moves before: Maia reads the last positions too
        after.push(move)
        return self._value(after, own_left, reach)

    def _note(
        self, board: chess.Board, candidates: list[Line], values: list[float], reach: float
    ) -> None:
        """Remember our moves here that are worth more than the engine's best one."""
        line = [move.uci() for move in board.move_stack[len(self.start.move_stack) :]]
        best, best_value = candidates[0], values[0]
        for candidate, value in zip(candidates[1:], values[1:], strict=True):
            if value > best_value:
                found = _Found(reach, line, candidate.move, value, best.move, best_value)
                with self._lock:
                    self._found.append(found)

    def _candidates(self, board: chess.Board, *, first: bool) -> list[Line]:
        """The engine's best moves for us that stay within the budget, best first."""
        count = self.settings.candidates * self._widen if first else self.settings.deeper_candidates
        return [
            line for line in self._evaluate(board, count) if line.cp >= -self.settings.budget_cp
        ]

    def _likely_replies(self, board: chess.Board) -> list[tuple[chess.Move, float]]:
        """The model's likeliest moves, together reply_mass of its probability, at most
        max_replies."""
        ranked = sorted(self._probabilities(board).items(), key=lambda item: -item[1])
        chosen: list[tuple[chess.Move, float]] = []
        mass = 0.0
        for move, probability in ranked:
            chosen.append((move, probability))
            mass += probability
            if mass >= self.settings.reply_mass or len(chosen) >= self.settings.max_replies:
                break
        return chosen

    def _static(self, board: chess.Board) -> float:
        """Our winning chance by the engine's evaluation, where the search ends."""
        lines = self._evaluate(board, 1)
        return winning_chance(lines[0].cp) if lines else 0.5

    def _result(self, board: chess.Board) -> float:
        result = board.result(claim_draw=True)
        if result == "1/2-1/2":
            return 0.5
        return 1.0 if (result == "1-0") == (self.settings.us == chess.WHITE) else 0.0

    def _ply(self, board: chess.Board) -> int:
        """Moves played since the start."""
        return len(board.move_stack) - len(self.start.move_stack)

    # ------------------------------------------------------------- the engine and the model

    def _evaluate(self, board: chess.Board, count: int, depth: int | None = None) -> list[Line]:
        key = (board.fen(), depth or self.settings.depth, count)
        if key not in self._lines:
            with self.pool.borrow() as evaluator:
                self._lines[key] = evaluator.lines(board, depth=key[1], count=count)
        return self._lines[key]

    def _probabilities(self, board: chess.Board) -> dict[chess.Move, float]:
        key = board.fen()
        if key not in self._replies:
            self._replies[key] = self.model.probabilities(board, elo=self.settings.elo)
        return self._replies[key]

    # ------------------------------------------------------------- checking the tries

    def _checked(self) -> list[Try]:
        """The best tries, each evaluated at verify_depth; those beyond the budget there are
        dropped. With their refutation."""
        best_of: dict[tuple[tuple[str, ...], chess.Move], _Found] = {}
        for found in self._found:
            key = (tuple(found.line), found.move)
            if key not in best_of or found.reach > best_of[key].reach:
                best_of[key] = found
        tries: list[Try] = []
        for found in sorted(best_of.values(), key=lambda f: -f.rank):
            if len(tries) == self.settings.shown_tries:
                break
            board = self.start.copy()
            for uci in found.line:
                board.push_uci(uci)
            san, best_san = board.san(found.move), board.san(found.best_move)
            board.push(found.move)
            deep = self._evaluate(board, 1, depth=self.settings.verify_depth)
            cp = -deep[0].cp if deep else 0  # the opponent is to move there
            if cp < -self.settings.budget_cp:
                continue
            tries.append(
                Try(
                    line=found.line,
                    uci=found.move.uci(),
                    san=san,
                    cp=cp,
                    practical=found.value,
                    best_san=best_san,
                    best_practical=found.best_value,
                    reach=found.reach,
                    refutation=self._refutation(board),
                )
            )
        return tries

    def _refutation(self, board: chess.Board, plies: int = 8) -> list[RefutationStep]:
        """The engine's line after the try, with, at each of the opponent's moves, how likely
        the model plays one about as good as the engine's (within good_enough in winning
        chance)."""
        board = board.copy()
        steps = []
        for _ in range(plies):
            if board.is_game_over():
                break
            theirs = board.turn != self.settings.us
            lines = self._evaluate(board, 5 if theirs else 1)
            if not lines:
                break
            found = None
            if theirs:
                best = winning_chance(lines[0].cp)
                good = [
                    line.move
                    for line in lines
                    if winning_chance(line.cp) >= best - self.settings.good_enough
                ]
                probabilities = self._probabilities(board)
                found = sum(probabilities.get(move, 0.0) for move in good)
            steps.append(RefutationStep(board.san(lines[0].move), lines[0].move.uci(), found))
            board.push(lines[0].move)
        return steps


class StockfishEvaluator:
    """An Evaluator on one running Stockfish, best with one thread: the pool runs several."""

    def __init__(self, engine: chess.engine.SimpleEngine) -> None:
        self.engine = engine

    def lines(self, board: chess.Board, *, depth: int, count: int) -> list[Line]:
        infos = self.engine.analyse(board, chess.engine.Limit(depth=depth), multipv=count)
        result = []
        for info in infos:
            if "pv" in info and "score" in info:
                cp = info["score"].pov(board.turn).score(mate_score=MATE_CP)
                result.append(Line(info["pv"][0], cp if cp is not None else 0))
        return result


class MaiaModel:
    """Maia as the opponent model: a player of the rating facing one of the same rating."""

    def __init__(self, maia: Maia) -> None:
        self.maia = maia

    def probabilities(self, board: chess.Board, *, elo: int) -> dict[chess.Move, float]:
        return self.maia.probabilities(board, self_elo=elo, oppo_elo=elo)
