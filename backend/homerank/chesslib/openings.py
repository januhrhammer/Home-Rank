"""Opening names, from Lichess's opening list (ADR 0021).

The list names positions: each row is an ECO code, a name and the moves that reach the position.
A game is named after the last named position among its first moves, so a transposition gets the
name of the position it reaches, whatever the move order. The table is built once per process,
from the TSV files in data/openings (about a quarter of a second).
"""

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import chess
import chess.polyglot

from homerank.chesslib.positions import as_bigint

DATA = Path(__file__).parent / "data" / "openings"

# Half-moves of a game looked at: the list's longest line (a Marshall Attack) has 36.
MAX_PLIES = 40


@dataclass(frozen=True)
class Opening:
    eco: str
    name: str


@cache
def _table() -> dict[int, Opening]:
    """Each named position, by its hash as the database stores it (a signed 64-bit number)."""
    table = {}
    for path in sorted(DATA.glob("*.tsv")):
        with path.open(encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file, delimiter="\t"):
                board = chess.Board()
                for token in row["pgn"].split():
                    if not token[0].isdigit():  # skip the move numbers, "1." and "1..."
                        board.push_san(token)
                table[as_bigint(chess.polyglot.zobrist_hash(board))] = Opening(
                    row["eco"], row["name"]
                )
    return table


def opening_at(zobrist: int) -> Opening | None:
    """The name of this position, if the list has one; the hash as the database stores it."""
    return _table().get(zobrist)


def opening_of(positions: Iterable[int]) -> Opening | None:
    """A game's opening: the last named position among its first MAX_PLIES half-moves. The
    positions are the game's, in order from its start, hashed as the database stores them."""
    table = _table()
    found = None
    for ply, zobrist in enumerate(positions):
        if ply > MAX_PLIES:
            break
        found = table.get(zobrist, found)
    return found
