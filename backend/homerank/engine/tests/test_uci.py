import chess
import chess.engine
import pytest

from homerank.engine.uci import engine_name, open_engine

pytestmark = pytest.mark.engine

DEPTH = 8  # shallow: enough to see the engine work, and quick


def test_stockfish_runs_and_names_itself(stockfish: str) -> None:
    assert engine_name(stockfish).startswith("Stockfish ")


def test_the_engine_analyses_with_our_options(stockfish: str) -> None:
    # Stockfish refuses unknown options, so this also checks the names of the ones we set.
    with open_engine(stockfish, threads=2, hash_mb=32) as engine:
        info = engine.analyse(chess.Board(), chess.engine.Limit(depth=DEPTH))
    assert info["depth"] >= DEPTH
