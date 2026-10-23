import os
from pathlib import Path

import pytest

# Where `just stockfish` and `just maia` put them; CI and others may set STOCKFISH_PATH and
# MAIA_PATH instead.
TOOLS = Path(__file__).parents[4] / ".tools"
DOWNLOADED = TOOLS / "stockfish" / "stockfish"
MAIA_DOWNLOADED = TOOLS / "maia" / "maia3-5m.onnx"


@pytest.fixture(scope="session")
def stockfish() -> str:
    """The path of Stockfish, for tests marked `engine`."""
    path = os.environ.get("STOCKFISH_PATH") or str(DOWNLOADED)
    if not Path(path).exists() and os.sep in path:
        pytest.fail(f"Stockfish isn't at {path}: run `just stockfish` (or set STOCKFISH_PATH)")
    return path


@pytest.fixture(scope="session")
def maia_model() -> str:
    """The path of Maia's model, for tests marked `maia`."""
    path = os.environ.get("MAIA_PATH") or str(MAIA_DOWNLOADED)
    if not Path(path).exists():
        pytest.fail(f"Maia isn't at {path}: run `just maia` (or set MAIA_PATH)")
    return path
