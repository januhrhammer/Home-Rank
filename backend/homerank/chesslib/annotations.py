"""Annotating a game: its comments, variations and NAGs change, its main line never (ADR 0019).

A game's fingerprint (ADR 0008), its indexed positions and its engine analysis all come from its
starting position and main line, so as long as those stay, an annotated game is the same game.
"""

import io

import chess
import chess.pgn


class UnreadablePgnError(ValueError):
    def __init__(self) -> None:
        super().__init__("the annotated game isn't readable PGN")


class MainLineChangedError(ValueError):
    def __init__(self) -> None:
        super().__init__("the annotated game's start or main line differs from the game's")


def _read(text: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(text))
    if game is None or game.errors:
        raise UnreadablePgnError
    return game


def _main_line(game: chess.pgn.Game) -> tuple[str, list[chess.Move]]:
    return game.board().fen(), list(game.mainline_moves())


def annotated_pgn(stored: str, submitted: str) -> str:
    """The stored game with the submitted game's annotations: the submitted moves, comments,
    NAGs and variations under the stored game's headers.

    Raises UnreadablePgnError if `submitted` isn't one readable game, and MainLineChangedError
    if it starts elsewhere or its main line has other moves than the stored game's.
    """
    original = _read(stored)
    annotated = _read(submitted)
    if _main_line(annotated) != _main_line(original):
        raise MainLineChangedError
    # The headers are the stored game's: players, date, result, even a FEN, stay as they were.
    annotated.headers = original.headers.copy()
    exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
    return annotated.accept(exporter) + "\n"
