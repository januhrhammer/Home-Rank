import pytest

from homerank.chesslib.annotations import (
    MainLineChangedError,
    UnreadablePgnError,
    annotated_pgn,
)


def flat(text: str) -> str:
    """The text with its line breaks as spaces: python-chess wraps movetext at 80 columns."""
    return " ".join(text.split())


STORED = """[Event "Club championship"]
[White "Anna"]
[Black "Ben"]
[Result "1-0"]
[TimeControl "180+2"]

1. e4 { [%clk 0:03:00] } e5 { [%clk 0:02:59] } 2. Nf3 Nc6 3. Bb5 1-0
"""


def test_annotations_are_taken_with_the_stored_headers() -> None:
    submitted = """[White "someone else"]

{ A Ruy Lopez. } 1. e4 { [%clk 0:03:00] Best by test. } e5 { [%clk 0:02:59] }
2. Nf3 $1 ( 2. f4 { The King's Gambit. } ) 2... Nc6 3. Bb5 $14 1-0"""

    result = annotated_pgn(STORED, submitted)

    assert result.startswith('[Event "Club championship"]')
    assert '[White "Anna"]' in result
    assert "someone else" not in result
    assert '[TimeControl "180+2"]' in result
    assert "{ A Ruy Lopez. } 1. e4 { [%clk 0:03:00] Best by test. } 1... e5" in flat(result)
    assert "2. Nf3 $1 ( 2. f4 { The King's Gambit. } )" in flat(result)
    assert flat(result).endswith("3. Bb5 $14 1-0")


def test_annotations_can_be_removed_again() -> None:
    annotated = annotated_pgn(STORED, "1. e4 { Hi } e5 2. Nf3 ( 2. f4 ) 2... Nc6 3. Bb5 1-0")

    result = annotated_pgn(annotated, "1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0")

    assert flat(result).endswith("1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0")


@pytest.mark.parametrize(
    "submitted",
    [
        "1. e4 e5 2. Nf3 Nc6 1-0",  # a move fewer
        "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0",  # a move more
        "1. e4 e5 2. Nc3 Nc6 3. Bb5 1-0",  # another move
        "1. e4 e5 2. f4 ( 2. Nf3 Nc6 3. Bb5 ) 1-0",  # a variation promoted
        '[FEN "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"]\n[SetUp "1"]\n\n1. e4 1-0',  # another start
    ],
)
def test_the_main_line_cant_change(submitted: str) -> None:
    with pytest.raises(MainLineChangedError):
        annotated_pgn(STORED, submitted)


@pytest.mark.parametrize("submitted", ["", "1. e4 e5 2. Ke3", "not a game at all"])
def test_unreadable_games_are_refused(submitted: str) -> None:
    with pytest.raises((UnreadablePgnError, MainLineChangedError)):
        annotated_pgn(STORED, submitted)


def test_a_game_from_a_position_keeps_its_start() -> None:
    stored = '[FEN "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"]\n[SetUp "1"]\n\n1. e4 Kd7 *'

    result = annotated_pgn(stored, '[FEN "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"]\n\n1. e4 { ! } Kd7 *')

    assert '[FEN "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"]' in result
    assert flat(result).endswith("1. e4 { ! } 1... Kd7 *")
