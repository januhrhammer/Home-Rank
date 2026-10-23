import os
from pathlib import Path

import pytest

# Where `just stockfish` puts it; CI and others set STOCKFISH_PATH.
DOWNLOADED = Path(__file__).parents[4] / ".tools" / "stockfish" / "stockfish"


@pytest.fixture(scope="session")
def stockfish() -> str:
    """The path of Stockfish, for tests marked `engine`."""
    path = os.environ.get("STOCKFISH_PATH") or str(DOWNLOADED)
    if not Path(path).exists() and os.sep in path:
        pytest.fail(f"Stockfish isn't at {path}: run `just stockfish` (or set STOCKFISH_PATH)")
    return path
