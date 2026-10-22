import pytest

from homerank.chesslib.dedup import dedup_hash
from homerank.chesslib.headers import read_headers
from homerank.chesslib.tests.helpers import SCHOLARS_MATE, parse

# The fingerprint of SCHOLARS_MATE. Fingerprints are stored, so a change to what goes into them
# must be deliberate: raise dedup.VERSION and plan to recompute them, then update this value.
SCHOLARS_MATE_HASH = "4e3fc189d0e5559189d9db57b1c3a8545151b81924898a1821c05695c4439751"


def fingerprint(pgn: str) -> str:
    game = parse(pgn)
    return dedup_hash(game, read_headers(game))


def test_the_fingerprint_is_stable() -> None:
    assert fingerprint(SCHOLARS_MATE) == SCHOLARS_MATE_HASH


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('[Event "Casual game"]', '[Event "Club championship"]'),
        ('[Site "Hamburg"]', '[Site "?"]'),
        ('[White "Anna"]', '[White "  ANNA "]'),  # the same name, written differently
        ("2. Bc4", "2. Bc4 {the main idea} (2. Nf3 Nc6)"),  # comments and variations
        ("1. e4", "1. e4 $1"),
    ],
)
def test_same_game(old: str, new: str) -> None:
    assert old in SCHOLARS_MATE
    assert fingerprint(SCHOLARS_MATE.replace(old, new)) == SCHOLARS_MATE_HASH


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('[White "Anna"]', '[White "Anne"]'),
        ('[Black "Ben"]', '[Black "Benjamin"]'),
        ('[Date "2024.03.05"]', '[Date "2024.03.06"]'),
        ('[Date "2024.03.05"]', '[Date "2024.??.??"]'),
        ('[Result "1-0"]', '[Result "1/2-1/2"]'),
        ("4. Qxf7# 1-0", "1-0"),  # one move fewer
    ],
)
def test_different_game(old: str, new: str) -> None:
    assert old in SCHOLARS_MATE
    assert fingerprint(SCHOLARS_MATE.replace(old, new)) != SCHOLARS_MATE_HASH


def test_white_and_black_are_not_interchangeable() -> None:
    players = '[White "Anna"]\n[Black "Ben"]'
    swapped = SCHOLARS_MATE.replace(players, '[White "Ben"]\n[Black "Anna"]')
    assert players in SCHOLARS_MATE

    assert fingerprint(swapped) != SCHOLARS_MATE_HASH


def test_the_starting_position_counts() -> None:
    """The same moves from another starting position, as in Chess960, are another game."""
    chess960 = """\
[White "Anna"]
[Black "Ben"]
[Date "2024.03.05"]
[Result "*"]
[Variant "Chess960"]
[SetUp "1"]
[FEN "bqnrkrnb/pppppppp/8/8/8/8/PPPPPPPP/BQNRKRNB w KQkq - 0 1"]

1. e4 e5 *
"""
    standard = SCHOLARS_MATE.replace('[Result "1-0"]', '[Result "*"]').replace(
        "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0", "1. e4 e5 *"
    )

    assert fingerprint(chess960) != fingerprint(standard)
