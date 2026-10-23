"""Repertoires as moves between positions (ADR 0016): reading them from PGN, and finding what
the starting position still leads to.

A move is identified by the position it is played from and the move itself, so the same
position reached by different move orders has one set of moves.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

import chess
import chess.pgn
import chess.polyglot

START_ZOBRIST = chess.polyglot.zobrist_hash(chess.Board())


class NotFromStartError(ValueError):
    """A game that doesn't start from the starting position, which every repertoire does."""


@dataclass(frozen=True)
class Edge:
    """A move from one position to the next. Hashes are unsigned 64-bit Polyglot hashes."""

    from_zobrist: int
    from_fen: str
    move_uci: str
    move_san: str
    to_zobrist: int
    comment: str = ""


def edge(board: chess.Board, move: chess.Move, comment: str = "") -> Edge:
    """The move played on the board; the board stays as it was. The move must be legal."""
    after = board.copy(stack=False)
    after.push(move)
    return Edge(
        from_zobrist=chess.polyglot.zobrist_hash(board),
        from_fen=board.fen(),
        move_uci=move.uci(),
        move_san=board.san(move),
        to_zobrist=chess.polyglot.zobrist_hash(after),
        comment=comment,
    )


def pgn_edges(game: chess.pgn.Game, seen: set[tuple[int, str]] | None = None) -> list[Edge]:
    """Every move of the game, its variations included, once. A move's comment is the one
    after it in the PGN. The game must start from the starting position.

    Moves whose (from_zobrist, move_uci) is in seen are left out, and those returned are added
    to it: reading many games, such as a course whose chapters replay their lines from the
    first move, then skips what is known without working out its FEN and SAN again.
    """
    if game.board() != chess.Board():
        raise NotFromStartError
    seen = set() if seen is None else seen
    edges = []
    # Each node with the board after it and its hash, so that nothing is worked out twice.
    start = game.board()
    stack: list[tuple[chess.pgn.GameNode, chess.Board, int]] = [
        (game, start, chess.polyglot.zobrist_hash(start))
    ]
    while stack:
        node, board, zobrist = stack.pop()
        children: list[tuple[chess.pgn.GameNode, chess.Board, int]] = []
        for child in node.variations:
            after = board.copy(stack=False)
            after.push(child.move)
            after_zobrist = chess.polyglot.zobrist_hash(after)
            children.append((child, after, after_zobrist))
            key = (zobrist, child.move.uci())
            if key not in seen:
                seen.add(key)
                edges.append(
                    Edge(
                        from_zobrist=zobrist,
                        from_fen=board.fen(),
                        move_uci=key[1],
                        move_san=board.san(child.move),
                        to_zobrist=after_zobrist,
                        comment=child.comment.strip(),
                    )
                )
        stack.extend(reversed(children))  # the main line first
    return edges


def reachable(edges: Iterable[tuple[int, str, int]], start: int) -> set[tuple[int, str]]:
    """The moves, given as (from_zobrist, move_uci, to_zobrist), that can be reached from the
    start position; as (from_zobrist, move_uci)."""
    moves_from = defaultdict(list)
    for from_zobrist, move_uci, to_zobrist in edges:
        moves_from[from_zobrist].append((move_uci, to_zobrist))
    seen_positions = {start}
    found = set()
    todo = [start]
    while todo:
        position = todo.pop()
        for move_uci, to_zobrist in moves_from[position]:
            found.add((position, move_uci))
            if to_zobrist not in seen_positions:
                seen_positions.add(to_zobrist)
                todo.append(to_zobrist)
    return found
