"""The facts Home-Rank stores about a game, cleaned up from its PGN headers.

PGN headers are free text: "?" or an empty value mean unknown, dates may lack the month or the
day, ratings may be "0", and time controls come in several formats. This module turns them into
plain values, with None or "" for anything unknown.
"""

import datetime
import re
from dataclasses import dataclass
from enum import StrEnum

import chess.pgn

RESULTS = ("1-0", "0-1", "1/2-1/2")
_ECO = re.compile(r"[A-E]\d\d")
_DATE = re.compile(r"(\d{4}|\?{4})[.\-/](\d\d|\?\?)[.\-/](\d\d|\?\?)")
_MONTHS = range(1, 13)
# Ratings beyond any platform's record (a typo, or another number in the Elo header) are unknown.
_RATINGS = range(1, 4001)
# Lichess's limits for the estimated duration of a game, in seconds (see time_class).
_BULLET_UNDER = 3 * 60
_BLITZ_UNDER = 8 * 60
_RAPID_UNDER = 25 * 60


class TimeClass(StrEnum):
    BULLET = "bullet"
    BLITZ = "blitz"
    RAPID = "rapid"
    CLASSICAL = "classical"
    CORRESPONDENCE = "correspondence"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PgnDate:
    """A date in which the year, month or day may be unknown, as PGN allows ("1960.??.??")."""

    year: int | None = None
    month: int | None = None
    day: int | None = None

    def __str__(self) -> str:
        """In PGN's notation, e.g. "1960.??.??"."""
        year = "????" if self.year is None else f"{self.year:04}"
        month = "??" if self.month is None else f"{self.month:02}"
        day = "??" if self.day is None else f"{self.day:02}"
        return f"{year}.{month}.{day}"

    def earliest(self) -> datetime.date | None:
        """The first day the date could mean, for sorting and filtering; None without a year."""
        if self.year is None:
            return None
        return datetime.date(self.year, self.month or 1, self.day or 1)


@dataclass(frozen=True)
class GameHeaders:
    white: str
    black: str
    white_elo: int | None
    black_elo: int | None
    result: str  # one of RESULTS, or "*" if unknown or unfinished
    date: PgnDate
    event: str
    site: str
    eco: str
    opening: str
    time_control: str
    time_class: TimeClass
    termination: str


def read_headers(game: chess.pgn.Game) -> GameHeaders:
    headers = game.headers
    time_control = _text(headers.get("TimeControl"))
    return GameHeaders(
        white=_text(headers.get("White")),
        black=_text(headers.get("Black")),
        white_elo=_rating(headers.get("WhiteElo")),
        black_elo=_rating(headers.get("BlackElo")),
        result=_result(headers.get("Result")),
        date=_date(headers),
        event=_text(headers.get("Event")),
        site=_text(headers.get("Site")),
        eco=_eco(headers.get("ECO")),
        opening=_text(headers.get("Opening")),
        time_control=time_control,
        time_class=time_class(time_control),
        termination=_text(headers.get("Termination")),
    )


def parse_date(value: str) -> PgnDate:
    """A PGN date such as "2024.03.05" or "1960.??.??". Impossible parts count as unknown."""
    match = _DATE.fullmatch(value.strip())
    if match is None:
        return PgnDate()
    year, month, day = (None if part.startswith("?") else int(part) for part in match.groups())
    if year is None or year == 0:
        return PgnDate()
    if month is None or month not in _MONTHS:
        return PgnDate(year)
    try:
        datetime.date(year, month, day or 1)
    except ValueError:
        return PgnDate(year, month)  # e.g. 30 February
    return PgnDate(year, month, day)


def time_class(time_control: str) -> TimeClass:
    """The kind of game a PGN TimeControl describes, as Lichess classifies them.

    Lichess estimates a game's duration as the base time plus 40 times the increment, in
    seconds: under 3 minutes is bullet, under 8 blitz, under 25 rapid, otherwise classical.
    A time control of one move per period ("1/86400", a day per move) is correspondence.
    """
    # Only the first period counts, e.g. "40/7200" in "40/7200:3600": it sets the pace.
    period = time_control.partition(":")[0].strip()
    match = re.fullmatch(r"(?:(\d+)/)?\*?(\d+)(?:\+(\d+))?", period)
    if match is None:
        return TimeClass.UNKNOWN
    moves, base, increment = match.groups()
    if moves == "1":
        return TimeClass.CORRESPONDENCE
    estimate = int(base) + 40 * int(increment or 0)
    if estimate < _BULLET_UNDER:
        return TimeClass.BULLET
    if estimate < _BLITZ_UNDER:
        return TimeClass.BLITZ
    if estimate < _RAPID_UNDER:
        return TimeClass.RAPID
    return TimeClass.CLASSICAL


def _date(headers: chess.pgn.Headers) -> PgnDate:
    # python-chess fills in a missing Date as "????.??.??"; Lichess also writes UTCDate.
    date = parse_date(headers.get("Date", ""))
    return date if date.year is not None else parse_date(headers.get("UTCDate", ""))


def _text(value: str | None) -> str:
    value = (value or "").strip()
    return "" if value == "?" else value


def _rating(value: str | None) -> int | None:
    value = _text(value)
    return int(value) if value.isdigit() and int(value) in _RATINGS else None


def _result(value: str | None) -> str:
    value = _text(value)
    return value if value in RESULTS else "*"


def _eco(value: str | None) -> str:
    value = _text(value).upper()
    return value if _ECO.fullmatch(value) else ""
