import datetime

import pytest

from homerank.chesslib.headers import PgnDate, TimeClass, parse_date, read_headers, time_class
from homerank.chesslib.tests.helpers import SCHOLARS_MATE, parse

CHESS_COM = """\
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2024.01.31"]
[White "Hikaru"]
[Black "MagnusCarlsen"]
[Result "1/2-1/2"]
[WhiteElo "3254"]
[BlackElo "3235"]
[TimeControl "180+1"]
[ECO "B23"]
[Termination "Game drawn by repetition"]

1. e4 c5 1/2-1/2
"""


def test_reads_the_headers() -> None:
    headers = read_headers(parse(CHESS_COM))

    assert headers.white == "Hikaru"
    assert headers.black == "MagnusCarlsen"
    assert (headers.white_elo, headers.black_elo) == (3254, 3235)
    assert headers.result == "1/2-1/2"
    assert headers.date == PgnDate(2024, 1, 31)
    assert (headers.event, headers.site) == ("Live Chess", "Chess.com")
    assert headers.eco == "B23"
    assert headers.time_control == "180+1"
    assert headers.time_class == TimeClass.BLITZ
    assert headers.termination == "Game drawn by repetition"


def test_unknown_values_are_empty() -> None:
    pgn = """\
[Event "?"]
[White "?"]
[Black ""]
[Result "?"]
[WhiteElo "0"]
[BlackElo "-"]
[ECO "X99"]
[Date "????.??.??"]

*
"""
    headers = read_headers(parse(pgn))

    assert (headers.event, headers.white, headers.black) == ("", "", "")
    assert headers.result == "*"
    assert (headers.white_elo, headers.black_elo) == (None, None)
    assert headers.eco == ""
    assert headers.date == PgnDate()
    assert headers.time_class == TimeClass.UNKNOWN
    assert headers.opening == ""


def test_lowercase_eco_and_utc_date() -> None:
    pgn = '[ECO "c45"]\n[UTCDate "2023.11.02"]\n\n*\n'

    headers = read_headers(parse(pgn))

    assert headers.eco == "C45"
    assert headers.date == PgnDate(2023, 11, 2)


@pytest.mark.parametrize(
    ("value", "expected", "as_pgn"),
    [
        ("2024.03.05", PgnDate(2024, 3, 5), "2024.03.05"),
        ("1960.??.??", PgnDate(1960), "1960.??.??"),
        ("1960.05.??", PgnDate(1960, 5), "1960.05.??"),
        ("2024-03-05", PgnDate(2024, 3, 5), "2024.03.05"),
        ("2023.02.30", PgnDate(2023, 2), "2023.02.??"),  # no 30 February
        ("2023.13.01", PgnDate(2023), "2023.??.??"),
        ("????.03.05", PgnDate(), "????.??.??"),  # a day without a year means nothing
        ("0000.00.00", PgnDate(), "????.??.??"),
        ("last Tuesday", PgnDate(), "????.??.??"),
    ],
)
def test_parses_dates(value: str, expected: PgnDate, as_pgn: str) -> None:
    date = parse_date(value)

    assert date == expected
    assert str(date) == as_pgn


def test_earliest_day_of_a_date() -> None:
    assert PgnDate(2024, 3, 5).earliest() == datetime.date(2024, 3, 5)
    assert PgnDate(1960).earliest() == datetime.date(1960, 1, 1)
    assert PgnDate(1960, 5).earliest() == datetime.date(1960, 5, 1)
    assert PgnDate().earliest() is None


@pytest.mark.parametrize(
    ("time_control", "expected"),
    [
        ("60", TimeClass.BULLET),
        ("120+1", TimeClass.BULLET),  # 160 seconds
        ("180", TimeClass.BLITZ),
        ("300+3", TimeClass.BLITZ),  # 420 seconds
        ("480", TimeClass.RAPID),
        ("600+5", TimeClass.RAPID),  # 800 seconds
        ("900+10", TimeClass.RAPID),  # 1300 seconds
        ("1500", TimeClass.CLASSICAL),
        ("5400+30", TimeClass.CLASSICAL),
        ("40/7200:3600", TimeClass.CLASSICAL),  # the first period sets the pace
        ("*60", TimeClass.BULLET),  # sandclock
        ("1/86400", TimeClass.CORRESPONDENCE),  # a day per move
        ("-", TimeClass.UNKNOWN),
        ("?", TimeClass.UNKNOWN),
        ("", TimeClass.UNKNOWN),
        ("blitz", TimeClass.UNKNOWN),
    ],
)
def test_time_class(time_control: str, expected: TimeClass) -> None:
    assert time_class(time_control) == expected


def test_scholars_mate_has_no_time_control() -> None:
    headers = read_headers(parse(SCHOLARS_MATE))

    assert headers.time_control == ""
    assert headers.time_class == TimeClass.UNKNOWN


def test_result_from_the_moves_when_the_header_is_unknown() -> None:
    """python-chess takes the result at the end of the moves when the Result header is "*"."""
    pgn = SCHOLARS_MATE.replace('[Result "1-0"]', '[Result "*"]')

    assert read_headers(parse(pgn)).result == "1-0"
