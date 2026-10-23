import json
import random
from collections import Counter
from pathlib import Path

import chess
import numpy as np
import pytest

from homerank.engine.maia import HISTORY, GameOverError, Maia, encode, load, sample

pytestmark = pytest.mark.maia

# The official model's answers (PyTorch, Maia's own encoding) for positions from random games
# at several ratings, written by docker/convert-maia.py when it converted the model.
EXPECTED = json.loads((Path(__file__).parent / "fixtures" / "maia3-5m-expected.json").read_text())


@pytest.fixture(scope="module")
def maia(maia_model: str) -> Maia:
    return load(maia_model)


def board_after(moves: list[str], fen: str = chess.STARTING_FEN) -> chess.Board:
    board = chess.Board(fen)
    for move in moves:
        board.push_uci(move)
    return board


def test_it_gives_the_official_models_probabilities(maia: Maia) -> None:
    for case in EXPECTED:
        board = board_after(case["moves"])
        probabilities = maia.probabilities(
            board, self_elo=case["self_elo"], oppo_elo=case["oppo_elo"]
        )
        for uci, expected in case["top"]:
            assert probabilities[chess.Move.from_uci(uci)] == pytest.approx(expected, abs=1e-4), (
                f"{uci} after {' '.join(case['moves']) or 'the start'}"
            )


def test_the_probabilities_are_for_the_legal_moves_and_add_up(maia: Maia) -> None:
    board = board_after(["e2e4", "e7e5", "g1f3"])

    probabilities = maia.probabilities(board, self_elo=1500, oppo_elo=1500)

    assert set(probabilities) == set(board.legal_moves)
    assert sum(probabilities.values()) == pytest.approx(1.0)


def test_promotions_are_decoded_for_both_sides(maia: Maia) -> None:
    # Each side has a pawn about to promote, and little else to do.
    white = chess.Board("8/P6k/8/8/8/8/8/K7 w - - 0 1")
    black = chess.Board("k7/8/8/8/8/8/p6K/8 b - - 0 1")

    white_moves = maia.probabilities(white, self_elo=1500, oppo_elo=1500)
    black_moves = maia.probabilities(black, self_elo=1500, oppo_elo=1500)

    assert max(white_moves, key=white_moves.__getitem__) == chess.Move.from_uci("a7a8q")
    assert max(black_moves, key=black_moves.__getitem__) == chess.Move.from_uci("a2a1q")


def test_a_game_from_a_position_works_without_earlier_moves(maia: Maia) -> None:
    # A game that starts from a FEN has no history before it; the model still answers.
    board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3")

    probabilities = maia.probabilities(board, self_elo=1500, oppo_elo=1500)

    assert sum(probabilities.values()) == pytest.approx(1.0)


def test_choosing_a_move_plays_a_legal_one(maia: Maia) -> None:
    board = board_after(["e2e4", "e7e5"])

    move = maia.choose_move(board, self_elo=1500, oppo_elo=1500, rng=random.Random(1))

    assert move in board.legal_moves


E4, D4, A3 = (chess.Move.from_uci(uci) for uci in ("e2e4", "d2d4", "a2a3"))
PROBABILITIES = {E4: 0.6, D4: 0.3, A3: 0.1}


def test_sampling_picks_moves_about_as_often_as_their_probability() -> None:
    rng = random.Random(7)

    picked = Counter(sample(PROBABILITIES, rng=rng) for _ in range(10_000))

    for move, probability in PROBABILITIES.items():
        assert picked[move] / 10_000 == pytest.approx(probability, abs=0.02)


def test_a_lower_temperature_favours_the_likeliest_moves() -> None:
    rng = random.Random(7)

    picked = Counter(sample(PROBABILITIES, rng=rng, temperature=0.5) for _ in range(10_000))

    # At 0.5 the weights are squared: 0.36, 0.09, 0.01 → e4 in 0.36 / 0.46 of the picks.
    assert picked[E4] / 10_000 == pytest.approx(0.36 / 0.46, abs=0.02)
    assert picked[A3] < picked[D4]


def test_temperature_zero_always_picks_the_likeliest_move() -> None:
    rng = random.Random(7)

    assert {sample(PROBABILITIES, rng=rng, temperature=0) for _ in range(100)} == {E4}


def test_no_move_when_the_game_is_over(maia: Maia) -> None:
    mated = board_after(["f2f3", "e7e5", "g2g4", "d8h4"])

    assert maia.probabilities(mated, self_elo=1500, oppo_elo=1500) == {}
    with pytest.raises(GameOverError):
        maia.choose_move(mated, self_elo=1500, oppo_elo=1500, rng=random.Random(1))


def test_the_input_holds_the_last_positions_oldest_first() -> None:
    board = board_after(["e2e4", "e7e5", "g1f3"])

    tokens = encode(board)

    assert tokens.shape == (1, 64, 12 * HISTORY + 1)
    # Fewer than 8 positions: the first one (the start) fills the oldest places.
    start, current = tokens[0, :, :12], tokens[0, :, 12 * (HISTORY - 1) : 12 * HISTORY]
    assert np.array_equal(start, tokens[0, :, 12 : 2 * 12])
    # Black is to move, so the board is seen from Black's side: Black's king (the side to
    # move's king, plane 5) stands on e1 of the mirrored board.
    assert current[chess.E1, 5] == 1
    assert tokens[0, :, -1].sum() == 0  # the thinking-time column
