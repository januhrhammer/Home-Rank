from datetime import datetime

import chess
from django.utils import timezone
from ninja import Field, Schema

from homerank.chesslib.players import Side
from homerank.play import services
from homerank.play.models import BotGame, BotGameStatus, Opponent, Termination


class OpponentOut(Schema):
    opponent: Opponent
    min_elo: int
    max_elo: int


class ClockIn(Schema):
    base_seconds: int = Field(ge=1, le=services.MAX_CLOCK_MS // 1000)
    increment_seconds: int = Field(ge=0, le=services.MAX_INCREMENT_MS // 1000)


class GameIn(Schema):
    start_fen: str = Field(chess.STARTING_FEN, max_length=100)
    start_label: str = Field("", max_length=200, examples=["Sicilian, after 1. e4 c5"])
    user_color: Side
    opponent: Opponent
    opponent_elo: int
    clock: ClockIn | None = None  # untimed


class MoveIn(Schema):
    move_uci: str = Field(max_length=5, examples=["e2e4"])


class ClockOut(Schema):
    """Each side's time left when the answer was made; the side to move's is running."""

    base_ms: int
    increment_ms: int
    white_ms: int
    black_ms: int


class BotGameOut(Schema):
    id: int
    start_fen: str
    start_label: str
    user_color: Side
    opponent: Opponent
    opponent_elo: int
    opponent_name: str  # e.g. "Maia 1500"
    moves: list[str]  # UCI, from start_fen
    fen: str  # the position now
    status: BotGameStatus
    result: str  # "1-0", "0-1", "1/2-1/2", or "" while playing
    termination: Termination | None
    clock: ClockOut | None  # untimed: none
    created_at: datetime
    finished_at: datetime | None
    saved_game_id: int | None  # the game it was saved as, among your games

    @staticmethod
    def resolve_opponent_name(game: BotGame) -> str:
        return services.opponent_name(game)

    @staticmethod
    def resolve_fen(game: BotGame) -> str:
        return services.board_of(game).fen()

    @staticmethod
    def resolve_termination(game: BotGame) -> str | None:
        return game.termination or None

    @staticmethod
    def resolve_clock(game: BotGame) -> ClockOut | None:
        clock = services.clock_at(game, timezone.now())
        if clock is None or game.clock_base_ms is None or game.clock_increment_ms is None:
            return None
        return ClockOut(
            base_ms=game.clock_base_ms,
            increment_ms=game.clock_increment_ms,
            white_ms=clock.white_ms,
            black_ms=clock.black_ms,
        )


class SavedOut(Schema):
    game_id: int  # among your games
