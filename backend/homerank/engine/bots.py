"""Opponents to play against (ADR 0017): Maia, which plays like a person of a given rating, and
Stockfish with its strength limited, for opponents stronger than Maia's range.

Both answer one question, the move to play in a position, so a game doesn't need to know which
one it is playing.
"""

import random
from dataclasses import dataclass, field
from typing import Protocol

import chess
import chess.engine

from homerank.engine.maia import GameOverError, Maia
from homerank.engine.uci import open_engine

# The range of Stockfish's UCI_Elo option (Stockfish 19). Its scale is that of engine rating
# lists, not of online players: see ADR 0017 for how Maia's ratings compare.
STOCKFISH_MIN_ELO = 1320
STOCKFISH_MAX_ELO = 3190


class Bot(Protocol):
    def move(self, board: chess.Board) -> chess.Move:
        """The bot's move in the position on `board`, for the side to move."""
        ...


@dataclass
class MaiaBot:
    """Maia playing as a person rated `elo` would, against an opponent rated `opponent_elo`."""

    model: Maia
    elo: int
    opponent_elo: int
    rng: random.Random = field(default_factory=random.Random)

    def move(self, board: chess.Board) -> chess.Move:
        return self.model.choose_move(
            board, self_elo=self.elo, oppo_elo=self.opponent_elo, rng=self.rng
        )


@dataclass
class StockfishBot:
    """Stockfish at `elo` on its own scale, thinking `seconds` per move."""

    path: str
    elo: int
    seconds: float = 0.2

    def move(self, board: chess.Board) -> chess.Move:
        with open_engine(self.path) as engine:
            engine.configure({"UCI_LimitStrength": True, "UCI_Elo": self.elo})
            result = engine.play(board, chess.engine.Limit(time=self.seconds))
        if result.move is None:  # only when there is no legal move
            raise GameOverError
        return result.move
