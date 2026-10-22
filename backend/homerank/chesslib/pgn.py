"""Reading PGN files one game at a time.

PGN files can be large, so games are read and handed out one by one, never the whole file at
once. Each game comes with its text exactly as it appears in the file, which Home-Rank stores
verbatim, and with python-chess's parsed version of it. A game that can't be read (an illegal
move, an unsupported variant) is reported with the reason, and reading continues with the next.
"""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TextIO, cast

import chess
import chess.pgn

# Comments ({...}, which may span lines, and ; to the end of the line) and escape lines (%).
_COMMENTS = re.compile(r"\{[^}]*(?:\}|$)|;[^\n]*|^%[^\n]*", re.MULTILINE)
# Everything python-chess understands in move text, and what it skips on purpose: move numbers
# ("12." and "12..."), check and mate signs, and "e.p." after an en passant capture.
_KNOWN_MOVETEXT = re.compile(
    rf"{chess.pgn.MOVETEXT_REGEX.pattern} | \d+\.+ | [+#] | e\.p\.", re.VERBOSE
)


@dataclass(frozen=True)
class PgnGame:
    """A game read from a PGN file."""

    line: int  # where the game starts in the file, counting from 1
    pgn: str  # the game's text, exactly as in the file
    game: chess.pgn.Game


@dataclass(frozen=True)
class PgnError:
    """A game that couldn't be read, and why."""

    line: int
    pgn: str
    reason: str


def read_pgn(lines: Iterable[bytes]) -> Iterator[PgnGame | PgnError]:
    """Read the games from a PGN file's lines, e.g. a file opened with open(path, "rb")."""
    recorder = _LineRecorder(lines)
    while True:
        recorder.start_game()
        # read_game only ever calls readline(), which is all the recorder provides.
        game = chess.pgn.read_game(cast(TextIO, recorder), Visitor=_GameBuilder)
        if game is None:
            return
        line, pgn = recorder.recorded_game()
        reason = _problem(game, pgn)
        if reason is None:
            yield PgnGame(line=line, pgn=pgn, game=game)
        else:
            yield PgnError(line=line, pgn=pgn, reason=reason)


class _GameBuilder(chess.pgn.GameBuilder[chess.pgn.Game]):
    """python-chess's game builder, without logging each error: read_pgn reports them."""

    def handle_error(self, error: Exception) -> None:
        self.game.errors.append(error)


def _problem(game: chess.pgn.Game, pgn: str) -> str | None:
    """Why the game can't be used, or None if it can."""
    if game.errors:
        return str(game.errors[0])
    # python-chess silently skips text it doesn't recognise as part of the moves, such as a
    # move to a square that doesn't exist. The game would then be stored without that move.
    unknown = _unknown_movetext(pgn)
    if unknown is not None:
        return f"not a move: {unknown!r}"
    # python-chess also reads variants such as atomic or crazyhouse; Home-Rank handles standard
    # chess and Chess960, which use the same board.
    if game.board().uci_variant != chess.Board.uci_variant:
        return f"unsupported variant: {game.headers.get('Variant', '?')}"
    return None


def _unknown_movetext(pgn: str) -> str | None:
    """The first word in the game's moves that python-chess would skip, or None."""
    lines = pgn.splitlines(keepends=True)
    headers = 0
    while headers < len(lines) and lines[headers].startswith("["):
        headers += 1
    movetext = _COMMENTS.sub(" ", "".join(lines[headers:]))
    leftover = _KNOWN_MOVETEXT.sub(" ", movetext).split()
    return leftover[0] if leftover else None


def _decode(line: bytes) -> str:
    # Most PGN files are UTF-8; older ones, e.g. from ChessBase, are often Windows-1252.
    try:
        return line.decode("utf-8")
    except UnicodeDecodeError:
        return line.decode("cp1252", errors="replace")


class _LineRecorder:
    """Hands out a file's lines one at a time, remembering those of the current game."""

    def __init__(self, lines: Iterable[bytes]) -> None:
        self._lines = iter(lines)
        self._line_number = 0
        self._game_lines: list[str] = []
        self._game_start = 1

    def readline(self) -> str:
        line = next(self._lines, None)
        if line is None:
            return ""  # end of file, as for a real file
        self._line_number += 1
        text = _decode(line)
        if not self._game_lines and not text.strip():
            self._game_start = self._line_number + 1  # skip blank lines before a game
        else:
            self._game_lines.append(text)
        return text

    def start_game(self) -> None:
        self._game_lines = []
        self._game_start = self._line_number + 1

    def recorded_game(self) -> tuple[int, str]:
        """The current game's first line number and its text, without surrounding blank lines."""
        text = "".join(self._game_lines).removeprefix("﻿").strip()
        return self._game_start, text + "\n"
