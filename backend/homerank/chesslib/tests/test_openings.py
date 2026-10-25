"""Opening names by position, from Lichess's opening list (ADR 0021)."""

import chess
import chess.polyglot

from homerank.chesslib.openings import MAX_PLIES, Opening, opening_at, opening_of
from homerank.chesslib.positions import as_bigint


def hashes(sans: str) -> list[int]:
    """The positions of a game's moves, from the start, as the database stores them."""
    board = chess.Board()
    result = [as_bigint(chess.polyglot.zobrist_hash(board))]
    for san in sans.split():
        board.push_san(san)
        result.append(as_bigint(chess.polyglot.zobrist_hash(board)))
    return result


NAJDORF_ENGLISH = "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be3 e5 Nb3"


def test_every_opening_of_the_list_is_read() -> None:
    # 3,865 rows in the version shipped; a row the code couldn't play through would stop it.
    assert opening_at(hashes("e4 e5 Nf3 Nc6 Bb5")[-1]) == Opening("C60", "Ruy Lopez")
    assert opening_at(hashes("")[0]) is None  # the starting position has no name


def test_a_game_is_named_after_the_last_named_position_it_reaches() -> None:
    # The list names 6.Be3 e5 7.Nb3; the game goes on past it.
    opening = opening_of(hashes(f"{NAJDORF_ENGLISH} Be7 f3 O-O Qd2"))

    assert opening == Opening("B90", "Sicilian Defense: Najdorf Variation, English Attack")


def test_a_transposition_gets_the_name_of_the_position_it_reaches() -> None:
    queens_gambit = opening_of(hashes("d4 Nf6 c4 e6 Nc3 Bb4"))
    english_first = opening_of(hashes("c4 e6 Nc3 Nf6 d4 Bb4"))

    assert queens_gambit == english_first
    assert queens_gambit is not None
    assert queens_gambit.name.startswith("Nimzo-Indian Defense")


def test_without_a_named_position_there_is_no_name() -> None:
    assert opening_of(hashes("")) is None
    assert opening_of([]) is None


def test_only_the_opening_moves_count() -> None:
    # A named position reached after MAX_PLIES half-moves doesn't rename the game.
    start = hashes("")[0]
    ruy = hashes("e4 e5 Nf3 Nc6 Bb5")[-1]
    late = [start] * (MAX_PLIES + 1) + [ruy]

    assert opening_of(late) is None
