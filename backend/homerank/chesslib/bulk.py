"""Turning one game of a reference database into the rows an import writes.

Runs in the import's worker processes, one game at a time; everything here is plain Python data,
so it crosses process boundaries cheaply. Games are read with the same rules as the user's own
(homerank.chesslib.pgn, headers and dedup), so a reference game and a personal copy of it match.
"""

from collections.abc import Iterator
from dataclasses import dataclass

import chess
import chess.pgn
import chess.polyglot

from homerank.chesslib.dedup import dedup_hash
from homerank.chesslib.headers import GameHeaders, read_headers
from homerank.chesslib.packed import encode_move, pack_moves
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.chesslib.positions import as_bigint

# Positions indexed per game by default: the opening and early middlegame, where the explorer
# and position search are used most (ADR 0015).
DEFAULT_DEPTH = 30


@dataclass(frozen=True)
class IndexedPosition:
    zobrist: int  # Polyglot hash as PostgreSQL's signed bigint
    ply: int  # 0 is the starting position
    next_move: int | None  # the packed move played from it; None at the game's end


@dataclass(frozen=True)
class BulkGame:
    headers: GameHeaders
    moves: bytes  # packed, two bytes per half-move
    ply_count: int
    start_fen: str  # "" for the usual starting position
    dedup_hash: str
    positions: list[IndexedPosition]


@dataclass(frozen=True)
class BulkError:
    reason: str


def parse_game(text: bytes, *, depth: int = DEFAULT_DEPTH) -> BulkGame | BulkError:
    """One game's text (as split_games gives it) as rows; its positions up to `depth` plies
    (None: all of them)."""
    items = list(read_pgn(iter(text.splitlines(keepends=True))))
    if not items:
        return BulkError("no game found")
    item = items[0]
    if not isinstance(item, PgnGame):
        return BulkError(item.reason)
    game = item.game
    moves = list(game.mainline_moves())
    board = game.board()
    start_fen = "" if board.fen() == chess.STARTING_FEN else board.fen()
    headers = read_headers(game)
    return BulkGame(
        headers=headers,
        moves=pack_moves(moves),
        ply_count=len(moves),
        start_fen=start_fen,
        dedup_hash=dedup_hash(game, headers),
        positions=list(_positions(board, moves, depth)),
    )


def _positions(
    board: chess.Board, moves: list[chess.Move], depth: int | None
) -> Iterator[IndexedPosition]:
    last = len(moves) if depth is None else min(depth, len(moves))
    for ply in range(last + 1):
        move = moves[ply] if ply < len(moves) else None
        yield IndexedPosition(
            zobrist=as_bigint(chess.polyglot.zobrist_hash(board)),
            ply=ply,
            next_move=encode_move(move) if move is not None else None,
        )
        if move is not None:
            board.push(move)
