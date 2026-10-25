"""The novelty search (ADR 0022), with a scripted engine and opponent model, and once for real."""

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
from homerank.engine.tests.scripted import (
    AFTER_G4,
    ENGINE,
    MODEL,
    START,
    Overlap,
    ScriptedEngine,
    ScriptedModel,
    fen_after,
    lines,
)
from homerank.engine.uci import open_engine


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
    # The line goes on with our answers, which have no probability, between the opponent's.
    assert [step.found is None for step in g4.refutation[:4]] == [False, True, False, True]
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
