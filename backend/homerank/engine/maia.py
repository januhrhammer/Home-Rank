"""Maia, a model that plays the moves people of a given rating play (ADR 0017).

Maia-3 5M (https://github.com/CSSLab/maia3, AGPL-3.0) as ONNX, run by onnxruntime: given the
last 8 positions of a game and the ratings of both players, it gives each possible move a
probability. Sampling from those probabilities plays like a person of that rating, mistakes
included. `docker/get-maia.sh` downloads the model; this module is a port of Maia's own board
encoding and move decoding, without PyTorch.
"""

import random
from functools import cache

import chess
import numpy as np
import onnxruntime

# The model looks at this many positions: the current one and the ones before it.
HISTORY = 8

# A position is 64 squares by 12 kinds of piece (six for the side to move, six for the other),
# always seen from the side to move: with Black to move, the board is mirrored.
PIECE_PLANES = {
    chess.PAWN: 0,
    chess.KNIGHT: 1,
    chess.BISHOP: 2,
    chess.ROOK: 3,
    chess.QUEEN: 4,
    chess.KING: 5,
}


def _possible_moves() -> list[str]:
    """Every move the model has a probability for, in its order: from any square to any
    square, then the promotions from the 7th to the 8th rank (always White's, as the board is
    seen from the side to move)."""
    squares = [chess.square_name(square) for square in chess.SQUARES]
    moves = [start + end for start in squares for end in squares]
    moves += [f"{a}7{b}8{piece}" for a in "abcdefgh" for b in "abcdefgh" for piece in "qrbn"]
    return moves


MOVE_INDEX = {move: index for index, move in enumerate(_possible_moves())}


def _mirrored(uci: str) -> str:
    """A move as seen from the other side of the board: e7e5 → e2e4."""
    return uci[0] + str(9 - int(uci[1])) + uci[2] + str(9 - int(uci[3])) + uci[4:]


def _planes(board: chess.Board) -> np.ndarray:
    """One position as 64 by 12 zeros and ones, seen from the side to move."""
    if board.turn == chess.BLACK:
        board = board.mirror()
    planes = np.zeros((64, 12), np.float32)
    for square, piece in board.piece_map().items():
        planes[
            square, PIECE_PLANES[piece.piece_type] + (6 if piece.color == chess.BLACK else 0)
        ] = 1
    return planes


def encode(board: chess.Board) -> np.ndarray:
    """The model's input for the position on `board`: it and up to 7 positions before it,
    from the board's moves, oldest first. A game shorter than that repeats its first position,
    as Maia does. One more column (always 0) is the model's thinking time, which it predicts
    rather than reads."""
    history = board.copy()
    positions = [_planes(history)]
    while len(positions) < HISTORY and history.move_stack:
        history.pop()
        positions.insert(0, _planes(history))
    positions = [positions[0]] * (HISTORY - len(positions)) + positions
    return np.concatenate([*positions, np.zeros((64, 1), np.float32)], axis=1)[np.newaxis]


class GameOverError(ValueError):
    def __init__(self) -> None:
        super().__init__("no legal moves: the game is over")


class Maia:
    """The model, loaded once; it can answer for any number of games."""

    def __init__(self, model_path: str) -> None:
        options = onnxruntime.SessionOptions()
        # One position at a time takes milliseconds; more threads would only compete with the
        # other requests.
        options.intra_op_num_threads = 1
        self._session = onnxruntime.InferenceSession(
            model_path, options, providers=["CPUExecutionProvider"]
        )

    def probabilities(
        self, board: chess.Board, *, self_elo: int, oppo_elo: int
    ) -> dict[chess.Move, float]:
        """How likely a player rated `self_elo`, facing one rated `oppo_elo`, plays each legal
        move in the position on `board`."""
        legal = list(board.legal_moves)
        if not legal:
            return {}
        logits = self._session.run(
            ["logits_move"],
            {
                "tokens": encode(board),
                "self_elo": np.array([self_elo], np.int64),
                "oppo_elo": np.array([oppo_elo], np.int64),
            },
        )[0][0]
        if board.turn == chess.WHITE:
            indexes = [MOVE_INDEX[move.uci()] for move in legal]
        else:
            indexes = [MOVE_INDEX[_mirrored(move.uci())] for move in legal]
        chosen = logits[indexes]
        weights = np.exp(chosen - chosen.max())
        return dict(zip(legal, (weights / weights.sum()).tolist(), strict=True))

    def choose_move(
        self,
        board: chess.Board,
        *,
        self_elo: int,
        oppo_elo: int,
        rng: random.Random,
        temperature: float = 1.0,
    ) -> chess.Move:
        """A move for the side to move, played as such players play it (see `sample`)."""
        probabilities = self.probabilities(board, self_elo=self_elo, oppo_elo=oppo_elo)
        if not probabilities:
            raise GameOverError
        return sample(probabilities, rng=rng, temperature=temperature)


def sample(
    probabilities: dict[chess.Move, float], *, rng: random.Random, temperature: float = 1.0
) -> chess.Move:
    """One of the moves, each as often as its probability says at temperature 1; lower
    temperatures favour the likeliest moves, and 0 always picks the likeliest one."""
    if temperature <= 0:
        return max(probabilities, key=probabilities.__getitem__)
    moves = list(probabilities)
    weights = [probability ** (1 / temperature) for probability in probabilities.values()]
    return rng.choices(moves, weights)[0]


@cache
def load(model_path: str) -> Maia:
    """The model at `model_path`, loaded on first use and kept for the life of the process."""
    return Maia(model_path)
