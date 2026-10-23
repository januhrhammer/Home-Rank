import io

import chess
import chess.pgn
import chess.polyglot
import pytest

from homerank.chesslib.repertoire import (
    START_ZOBRIST,
    NotFromStartError,
    edge,
    pgn_edges,
    reachable,
)


def parse(text: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(text))
    assert game is not None
    return game


def test_an_edge_joins_two_positions() -> None:
    board = chess.Board()

    result = edge(board, chess.Move.from_uci("g1f3"), "flexible")

    assert result.from_zobrist == START_ZOBRIST
    assert result.from_fen == chess.STARTING_FEN
    assert (result.move_uci, result.move_san, result.comment) == ("g1f3", "Nf3", "flexible")
    board.push_uci("g1f3")
    assert result.to_zobrist == chess.polyglot.zobrist_hash(board)


def test_every_move_of_a_pgn_with_its_variations_and_comments() -> None:
    game = parse("1. e4 { main } e5 (1... c5 2. Nf3 (2. c3)) 2. Nf3 *")

    edges = pgn_edges(game)

    assert sorted(e.move_san for e in edges) == ["Nf3", "Nf3", "c3", "c5", "e4", "e5"]
    assert next(e for e in edges if e.move_san == "e4").comment == "main"


def test_transposed_move_orders_reach_the_same_position() -> None:
    one = pgn_edges(parse("1. d4 Nf6 2. c4 e6 *"))
    other = pgn_edges(parse("1. c4 e6 2. d4 Nf6 *"))

    assert one[-1].to_zobrist == other[-1].to_zobrist
    assert one[-1].from_zobrist != other[-1].from_zobrist


def test_a_pgn_from_another_position_is_refused() -> None:
    game = parse('[FEN "8/8/8/8/8/8/k7/K6R w - - 0 1"]\n[SetUp "1"]\n\n1. Rh2+ *')

    with pytest.raises(NotFromStartError):
        pgn_edges(game)


def test_reachable_moves_follow_the_graph_from_the_start() -> None:
    # 1 -a-> 2 -b-> 3, 3 -c-> 2 (back again), and 7 -d-> 8 which nothing leads to.
    edges = [(1, "a", 2), (2, "b", 3), (3, "c", 2), (7, "d", 8)]

    assert reachable(edges, start=1) == {(1, "a"), (2, "b"), (3, "c")}
