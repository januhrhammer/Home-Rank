"""Moves packed into two bytes each, for reference games stored by the million.

A move is its from square (6 bits), its to square (6 bits) and the piece a pawn becomes (3 bits:
python-chess's piece type, 0 if none). Little-endian, so a game of 80 half-moves takes 160 bytes,
about a fifth of its move text. Decoding needs the starting position only to replay the moves.
"""

import struct
from collections.abc import Iterable

import chess
import chess.pgn

_MOVE = struct.Struct("<H")


def encode_move(move: chess.Move) -> int:
    return move.from_square | move.to_square << 6 | (move.promotion or 0) << 12


def decode_move(code: int) -> chess.Move:
    promotion = code >> 12 & 0b111
    return chess.Move(code & 0b111111, code >> 6 & 0b111111, promotion or None)


def pack_moves(moves: Iterable[chess.Move]) -> bytes:
    return b"".join(_MOVE.pack(encode_move(move)) for move in moves)


def unpack_moves(data: bytes) -> list[chess.Move]:
    return [decode_move(code) for (code,) in _MOVE.iter_unpack(data)]


def san_moves(data: bytes, board: chess.Board | None = None) -> list[str]:
    """The packed moves in SAN, played from `board` (the usual start if None)."""
    board = board.copy() if board is not None else chess.Board()
    sans = []
    for move in unpack_moves(data):
        sans.append(board.san(move))
        board.push(move)
    return sans


def to_pgn(headers: dict[str, str], moves: bytes, start_fen: str = "") -> str:
    """A PGN text from headers and packed moves (from `start_fen` if not the usual start)."""
    game = chess.pgn.Game(headers=headers)
    if start_fen:
        game.setup(start_fen)
    node: chess.pgn.GameNode = game
    for move in unpack_moves(moves):
        node = node.add_main_variation(move)
    return str(game) + "\n"
