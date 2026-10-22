import chess
import chess.polyglot

from homerank.chesslib.positions import as_bigint, positions
from homerank.chesslib.tests.helpers import SCHOLARS_MATE, parse

STARTING_POSITION = 0x463B96181691FC9C  # the Polyglot hash of the initial position


def test_one_position_per_ply_and_the_final_one() -> None:
    result = positions(parse(SCHOLARS_MATE))

    assert [p.ply for p in result] == list(range(8))
    assert result[0].zobrist == STARTING_POSITION
    assert [p.move_san for p in result] == ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#", None]
    assert result[0].move_uci == "e2e4"
    assert result[-1].move_uci is None


def test_the_final_position_is_the_end_of_the_game() -> None:
    game = parse(SCHOLARS_MATE)

    final = positions(game)[-1]

    assert final.zobrist == chess.polyglot.zobrist_hash(game.end().board())


def test_variations_are_not_indexed() -> None:
    with_variation = SCHOLARS_MATE.replace("2. Bc4", "2. Bc4 (2. Nf3 Nc6)")

    assert positions(parse(with_variation)) == positions(parse(SCHOLARS_MATE))


def test_transpositions_have_the_same_hash() -> None:
    one = positions(parse("1. e4 e5 2. Nf3 Nc6 *\n"))
    other = positions(parse("1. Nf3 Nc6 2. e4 e5 *\n"))

    assert one[-1].zobrist == other[-1].zobrist


def test_castling_is_written_as_in_standard_chess() -> None:
    moves = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. O-O *\n"

    castling = positions(parse(moves))[6]

    assert (castling.move_san, castling.move_uci) == ("O-O", "e1g1")


def test_a_game_without_moves_has_its_starting_position() -> None:
    (only,) = positions(parse('[Result "*"]\n\n*\n'))

    assert (only.ply, only.zobrist, only.move_san) == (0, STARTING_POSITION, None)


def test_hashes_as_postgres_bigint() -> None:
    assert as_bigint(0) == 0
    assert as_bigint(2**63 - 1) == 2**63 - 1
    assert as_bigint(2**63) == -(2**63)
    assert as_bigint(2**64 - 1) == -1
    assert as_bigint(STARTING_POSITION) == STARTING_POSITION  # top bit not set
