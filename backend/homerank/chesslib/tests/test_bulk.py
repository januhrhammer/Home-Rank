import chess
import chess.polyglot

from homerank.chesslib.bulk import (
    BulkError,
    BulkGame,
    parse_chunk,
    parse_game,
    positions_from_packed,
    reindex_chunk,
)
from homerank.chesslib.packed import encode_move, unpack_moves
from homerank.chesslib.positions import as_bigint

SHA256_HEX_DIGITS = 64

FOOLS_MATE = (
    b'[White "Ben"]\n[Black "Anna"]\n[Result "0-1"]\n[Date "2024.03.06"]\n\n'
    b"1. f3 e5 2. g4 Qh4# 0-1\n"
)


def test_a_game_becomes_packed_moves_headers_and_positions() -> None:
    game = parse_game(FOOLS_MATE)

    assert isinstance(game, BulkGame)
    assert (game.headers.white, game.headers.black, game.headers.result) == ("Ben", "Anna", "0-1")
    moves = [m.uci() for m in unpack_moves(game.moves)]
    assert moves == ["f2f3", "e7e5", "g2g4", "d8h4"]
    assert game.ply_count == len(moves)
    assert game.start_fen == ""
    assert len(game.dedup_hash) == SHA256_HEX_DIGITS
    start = game.positions[0]
    assert start.zobrist == as_bigint(chess.polyglot.zobrist_hash(chess.Board()))
    assert start.next_move == encode_move(chess.Move.from_uci("f2f3"))
    assert [p.ply for p in game.positions] == [0, 1, 2, 3, 4]
    assert game.positions[-1].next_move is None  # the game ends there


def test_positions_stop_at_the_depth() -> None:
    game = parse_game(FOOLS_MATE, depth=2)

    assert isinstance(game, BulkGame)
    assert [p.ply for p in game.positions] == [0, 1, 2]
    assert game.positions[-1].next_move == encode_move(chess.Move.from_uci("g2g4"))


def test_a_game_from_a_position_keeps_its_fen() -> None:
    fen = "8/4P1k1/8/8/8/8/6K1/8 w - - 0 1"
    game = parse_game(f'[SetUp "1"]\n[FEN "{fen}"]\n\n1. e8=Q *\n'.encode())

    assert isinstance(game, BulkGame)
    assert game.start_fen == fen


def test_a_broken_game_says_why() -> None:
    result = parse_game(FOOLS_MATE.replace(b"Qh4#", b"Qh9"))

    assert isinstance(result, BulkError)
    assert result.reason


def test_no_game_at_all() -> None:
    assert parse_game(b"\n\n") == BulkError("no game found")


def test_a_chunk_keeps_its_offsets_and_order() -> None:
    results = parse_chunk([(0, FOOLS_MATE), (120, b'[White "X"]\n\n1. e5 *\n')])

    assert [offset for offset, _ in results] == [0, 120]
    assert isinstance(results[0][1], BulkGame)
    assert isinstance(results[1][1], BulkError)


def test_stored_games_give_the_same_positions_again() -> None:
    game = parse_game(FOOLS_MATE)
    assert isinstance(game, BulkGame)

    assert positions_from_packed(game.start_fen, game.moves) == game.positions
    assert reindex_chunk([(7, game.start_fen, game.moves)], depth=1) == [
        (7, game.positions[0].zobrist, 0, game.positions[0].next_move),
        (7, game.positions[1].zobrist, 1, game.positions[1].next_move),
    ]
