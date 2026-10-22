"""The position index: every position of a game's main line, and the move played from it.

Positions are identified by their Polyglot Zobrist hash, a 64-bit number that is the same for
the same position however it was reached. Finding the games that reached a position, or the
moves played from it, is then a lookup of that number.
"""

from dataclasses import dataclass

import chess.pgn
import chess.polyglot

_SIGN_BIT = 1 << 63


@dataclass(frozen=True)
class Position:
    ply: int  # half-moves played before this position; 0 is the starting position
    zobrist: int  # Polyglot hash, an unsigned 64-bit number
    move_san: str | None  # the move played from here, None after the game's last move
    move_uci: str | None


def positions(game: chess.pgn.Game) -> list[Position]:
    """The main line's positions, from the starting position to the final one."""
    board = game.board()
    result = []
    for ply, move in enumerate(game.mainline_moves()):
        zobrist = chess.polyglot.zobrist_hash(board)
        result.append(Position(ply, zobrist, board.san(move), board.uci(move)))
        board.push(move)
    final = Position(len(result), chess.polyglot.zobrist_hash(board), None, None)
    return [*result, final]


def as_bigint(zobrist: int) -> int:
    """The hash as a signed 64-bit number, which is how PostgreSQL's bigint stores it."""
    return zobrist - (1 << 64) if zobrist >= _SIGN_BIT else zobrist
