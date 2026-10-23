"""Starting Stockfish and talking to it over UCI, the protocol of chess engines.

python-chess does the talking; this module only starts and stops the engine with our options.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import chess.engine


@contextmanager
def open_engine(
    path: str, *, threads: int = 1, hash_mb: int = 16
) -> Iterator[chess.engine.SimpleEngine]:
    """Start the engine at `path` with `threads` CPU threads and a hash table of `hash_mb`
    MB, and stop it again when the block ends."""
    engine = chess.engine.SimpleEngine.popen_uci(path)
    try:
        engine.configure({"Threads": threads, "Hash": hash_mb})
        yield engine
    finally:
        engine.quit()


def engine_name(path: str) -> str:
    """The name and version the engine reports, e.g. "Stockfish 19"."""
    with open_engine(path) as engine:
        return engine.id.get("name", "unknown engine")
