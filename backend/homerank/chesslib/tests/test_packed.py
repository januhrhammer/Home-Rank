import chess

from homerank.chesslib.packed import (
    decode_move,
    encode_move,
    pack_moves,
    san_moves,
    to_pgn,
    unpack_moves,
)


def test_moves_round_trip_in_two_bytes_each() -> None:
    moves = [chess.Move.from_uci(uci) for uci in ("e2e4", "e7e5", "g1f3", "b8c6", "e1g1")]

    packed = pack_moves(moves)

    assert len(packed) == 2 * len(moves)
    assert unpack_moves(packed) == moves


def test_promotions_keep_their_piece() -> None:
    for uci in ("e7e8q", "e7e8n", "a2a1r", "h2h1b"):
        move = chess.Move.from_uci(uci)
        assert decode_move(encode_move(move)) == move


def test_packed_moves_read_as_san() -> None:
    moves = [chess.Move.from_uci(uci) for uci in ("f2f3", "e7e5", "g2g4", "d8h4")]

    assert san_moves(pack_moves(moves)) == ["f3", "e5", "g4", "Qh4#"]


def test_san_from_another_starting_position() -> None:
    board = chess.Board("8/4P1k1/8/8/8/8/6K1/8 w - - 0 1")

    assert san_moves(pack_moves([chess.Move.from_uci("e7e8q")]), board) == ["e8=Q"]


def test_packed_games_become_pgn_again() -> None:
    moves = [chess.Move.from_uci(uci) for uci in ("f2f3", "e7e5", "g2g4", "d8h4")]

    text = to_pgn({"White": "Ben", "Black": "Anna", "Result": "0-1"}, pack_moves(moves))

    assert '[White "Ben"]' in text
    assert text.rstrip().endswith("1. f3 e5 2. g4 Qh4# 0-1")


def test_pgn_from_another_starting_position_says_so() -> None:
    fen = "8/4P1k1/8/8/8/8/6K1/8 w - - 0 1"

    text = to_pgn({"Result": "*"}, pack_moves([chess.Move.from_uci("e7e8q")]), fen)

    assert f'[FEN "{fen}"]' in text
    assert "1. e8=Q" in text
