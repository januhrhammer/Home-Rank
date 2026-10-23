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
from homerank.chesslib.packed import encode_move, pack_moves, unpack_moves
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
    """The board's position and those after each move, up to `depth` plies, each with the move
    played from it."""
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


def parse_chunk(
    chunk: list[tuple[int, bytes]], depth: int = DEFAULT_DEPTH
) -> list[tuple[int, BulkGame | BulkError]]:
    """Parse a batch of games (offset and text, as split_games gives them) in a worker
    process; the offsets come back with them, in the same order."""
    return [(offset, parse_game(text, depth=depth)) for offset, text in chunk]


def positions_from_packed(
    start_fen: str, moves: bytes, depth: int = DEFAULT_DEPTH
) -> list[IndexedPosition]:
    """A stored game's positions, from its packed moves: to index games again without their
    PGN."""
    board = chess.Board(start_fen) if start_fen else chess.Board()
    return list(_positions(board, unpack_moves(moves), depth))


def reindex_chunk(
    games: list[tuple[int, str, bytes]], depth: int = DEFAULT_DEPTH
) -> list[tuple[int, int, int, int | None]]:
    """Positions of stored games (id, start FEN, packed moves) as staging rows, in a worker
    process."""
    return [
        (game_id, p.zobrist, p.ply, p.next_move)
        for game_id, start_fen, moves in games
        for p in positions_from_packed(start_fen, moves, depth)
    ]


# Entry points for worker processes, which take one argument: they live here, without Django,
# so that a freshly started ("spawned") worker can import them.


def parse_job(args: tuple[list[tuple[int, bytes]], int]) -> list[tuple[int, BulkGame | BulkError]]:
    return parse_chunk(*args)


def reindex_job(
    args: tuple[list[tuple[int, str, bytes]], int],
) -> list[tuple[int, int, int, int | None]]:
    return reindex_chunk(*args)
