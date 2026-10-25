"""The novelty search (ADR 0022), with a scripted engine and opponent model, and once for real."""

import threading
import time

import chess
import chess.engine
import pytest

from homerank.engine.maia import load
from homerank.engine.novelty import (
    EnginePool,
    Line,
    MaiaModel,
    Search,
    Settings,
    StockfishEvaluator,
    winning_chance,
)
from homerank.engine.uci import open_engine


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
    legal move at 0. Takes a little time, so that searches running at once overlap."""

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
        return [Line(first, 0)] if first else []


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


def search(
    script: dict[str, list[Line]] = ENGINE,
    deep: dict[str, list[Line]] | None = None,
    engines: int = 1,
    overlap: Overlap | None = None,
    **settings: object,
) -> Search:
    pool = EnginePool([ScriptedEngine(script, deep, overlap) for _ in range(engines)])
    return Search(
        chess.Board(START),
        Settings(us=chess.WHITE, elo=2000, **settings),  # type: ignore[arg-type]
        pool,
        ScriptedModel(MODEL),
    )


def test_a_try_is_a_worse_move_that_scores_better_against_the_opponent() -> None:
    (g4,) = search().run(1)

    assert (g4.san, g4.best_san, g4.line) == ("g4", "e4", [])
    assert g4.practical == pytest.approx(0.8 * winning_chance(250) + 0.2 * winning_chance(-120))
    assert g4.best_practical == pytest.approx(winning_chance(30))
    assert g4.cp == -120  # noqa: PLR2004 - checked again: Black's 1...d5 is +120


def test_the_refutation_says_how_likely_each_of_its_moves_is_found() -> None:
    (g4,) = search().run(1)

    # Only 1...d5 keeps Black's edge (1...e5 is 17 points of winning chance worse), and a 2000
    # plays it one time in five; the scripted moves after it are found every time.
    first = g4.refutation[0]
    assert (first.san, first.uci) == ("d5", "d7d5")
    assert first.found == pytest.approx(0.2)
    assert g4.refuted == pytest.approx(0.2)


def test_moves_beyond_the_budget_are_not_tried() -> None:
    # 1.f3 would win against this opponent (1...a6?? 2.e4 +9), but is -2 for the engine. Even
    # if checked deeper it were only -1, the search doesn't bet on it.
    deep = {fen_after("f3"): lines(fen_after("f3"), ("e5", 100))}

    assert "f3" not in [t.san for t in search(deep=deep).run(1)]
    assert "f3" in [t.san for t in search(deep=deep, budget_cp=250).run(1)]


def test_a_try_beyond_the_budget_when_checked_deeper_is_dropped() -> None:
    deep = {AFTER_G4: lines(AFTER_G4, ("d5", 180))}

    assert search(deep=deep).run(1) == []


def test_the_search_deepens_step_by_step_and_stops_when_asked() -> None:
    steps = [own for own, _ in search().steps()]
    assert steps == [2, 3, 4, 4]  # the last one with more candidates

    # Asked to stop once the first step is reported: the next one ends at once, unreported.
    stop = False
    stopped = search()
    stopped.should_stop = lambda: stop
    reported = []
    for own, _ in stopped.steps():
        reported.append(own)
        stop = True
    assert reported == [2]


def test_the_pools_engines_work_at_once() -> None:
    overlap = Overlap()
    search(engines=3, overlap=overlap).run(2)

    assert overlap.most > 1


@pytest.mark.engine
@pytest.mark.maia
def test_a_real_search_finds_tries(stockfish: str, maia_model: str) -> None:
    # The Smith-Morra position from the spike, where it found 10.b4; shallow, to be quick.
    board = chess.Board()
    morra = "e4 c5 d4 cxd4 c3 dxc3 Nxc3 Nc6 Nf3 d6 Bc4 e6 O-O Nf6 Qe2 Be7 Rd1 e5"
    for san in morra.split(" "):
        board.push_san(san)
    with open_engine(stockfish) as one, open_engine(stockfish) as two:
        pool = EnginePool([StockfishEvaluator(one), StockfishEvaluator(two)])
        settings = Settings(us=chess.WHITE, elo=2000, depth=8, verify_depth=12)
        found = Search(board, settings, pool, MaiaModel(load(maia_model))).run(2)

    assert found, "no tries in a position known to have some"
    for one_try in found:
        assert one_try.gain > 0
        assert one_try.cp >= -settings.budget_cp
        assert one_try.refutation
