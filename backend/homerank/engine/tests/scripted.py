"""A scripted engine and opponent model for testing the novelty search without Stockfish or
Maia, and a small scripted opening (ADR 0022)."""

import threading
import time

import chess

from homerank.engine.novelty import Line


def fen_after(*sans: str) -> str:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board.fen()


def lines(fen: str, *pairs: tuple[str, int]) -> list[Line]:
    board = chess.Board(fen)
    return [Line(board.parse_san(san), cp) for san, cp in pairs]


class Overlap:
    """Counts the engine searches running at the same time, and the most at once."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running = 0
        self.most = 0

    def __enter__(self) -> None:
        with self.lock:
            self.running += 1
            self.most = max(self.most, self.running)

    def __exit__(self, *_: object) -> None:
        with self.lock:
            self.running -= 1


class ScriptedEngine:
    """Answers from a script by position (and, if scripted, by depth); elsewhere the first
    legal move, at the evaluation of the last scripted position before. Takes a little time, so
    that searches running at once overlap."""

    def __init__(
        self,
        script: dict[str, list[Line]],
        deep: dict[str, list[Line]] | None = None,
        overlap: Overlap | None = None,
    ):
        self.script = script
        self.deep = deep or {}
        self.overlap = overlap or Overlap()

    def lines(self, board: chess.Board, *, depth: int, count: int) -> list[Line]:
        with self.overlap:
            time.sleep(0.002)
            return self._lines(board, depth, count)

    def _lines(self, board: chess.Board, depth: int, count: int) -> list[Line]:
        fen = board.fen()
        if depth >= 20 and fen in self.deep:  # noqa: PLR2004 - the check of the tries
            return self.deep[fen][:count]
        if fen in self.script:
            return self.script[fen][:count]
        first = next(iter(board.legal_moves), None)
        return [Line(first, self._inherited(board))] if first else []

    def _inherited(self, board: chess.Board) -> int:
        """An unscripted position keeps the evaluation of the last scripted one before it, as
        if nothing changed since (for the side to move now); 0 if there is none."""
        earlier = board.copy()
        while earlier.move_stack:
            earlier.pop()
            scripted = self.script.get(earlier.fen())
            if scripted:
                same_side = earlier.turn == board.turn
                return scripted[0].cp if same_side else -scripted[0].cp
        return 0


class ScriptedModel:
    """Probabilities from a script by position; elsewhere all on the first legal move."""

    def __init__(self, script: dict[str, dict[str, float]]):
        self.script = script

    def probabilities(self, board: chess.Board, *, elo: int) -> dict[chess.Move, float]:
        fen = board.fen()
        if fen in self.script:
            return {board.parse_san(san): p for san, p in self.script[fen].items()}
        first = next(iter(board.legal_moves))
        return {first: 1.0}


START = chess.STARTING_FEN
AFTER_G4 = fen_after("g4")

# White to move. The engine prefers 1.e4 (+30); 1.g4 is worse (Black's 1...d5 is +120 for
# Black), but a 2000 plays 1...e5 four times in five, after which White stands well (+250).
# 1.f3 would be worse still, beyond the budget of 150.
ENGINE = {
    START: lines(START, ("e4", 30), ("d4", 25), ("g4", -60), ("f3", -200)),
    AFTER_G4: lines(AFTER_G4, ("d5", 120), ("e5", -50)),
    fen_after("g4", "e5"): lines(fen_after("g4", "e5"), ("Bg2", 250)),
    fen_after("g4", "d5"): lines(fen_after("g4", "d5"), ("h3", -120)),
    fen_after("e4", "e5"): lines(fen_after("e4", "e5"), ("Nf3", 30)),
    fen_after("f3"): lines(fen_after("f3"), ("e5", 200)),
    fen_after("f3", "a6"): lines(fen_after("f3", "a6"), ("e4", 900)),
}
MODEL = {
    fen_after("e4"): {"e5": 1.0},
    AFTER_G4: {"e5": 0.8, "d5": 0.2},
    fen_after("f3"): {"a6": 1.0},  # a blunder the budget must not let us bet on
}
