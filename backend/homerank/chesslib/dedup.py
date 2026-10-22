"""The fingerprint that recognises a game imported twice.

Two games are the same if they have the same players, date and result, start from the same
position and have the same main line. Other headers don't count, because sources spell Event or
Site differently, and neither do comments and variations: an annotated copy of a game that is
already in the database is a duplicate. Player names count in their normalised form, so
"Carlsen, Magnus" and "carlsen,magnus" are the same player.

The fingerprints are stored, so changing what goes into them means computing them again for all
games. VERSION is part of every fingerprint to make such a change possible.
"""

import hashlib

import chess.pgn

from homerank.chesslib.headers import GameHeaders
from homerank.chesslib.players import normalise_name

VERSION = 1


def dedup_hash(game: chess.pgn.Game, headers: GameHeaders) -> str:
    """The game's fingerprint: 64 hexadecimal characters (SHA-256)."""
    board = game.board()
    start = board.epd()  # the starting position, without the move counters
    moves = []
    for move in game.mainline_moves():
        moves.append(board.uci(move))  # needs the position the move is played in
        board.push(move)
    fields = [
        f"v{VERSION}",
        normalise_name(headers.white),
        normalise_name(headers.black),
        str(headers.date),
        headers.result,
        start,
        " ".join(moves),
    ]
    return hashlib.sha256("\n".join(fields).encode()).hexdigest()
