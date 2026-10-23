from datetime import date, datetime

from ninja import Field, Schema

from homerank.engine.tactics import PuzzleKind
from homerank.training.models import Puzzle, ReviewLog


class PuzzleFilters(Schema):
    """Filters for puzzles; all optional, and combined with AND."""

    game: int | None = Field(None, description="Only puzzles from this game")
    kind: PuzzleKind | None = Field(None, description='E.g. "missed": only your own misses')
    theme: str | None = Field(None, description='E.g. "mateIn2" or "material"')
    eco: str | None = Field(None, description="Opening code or its start, e.g. B or B90")
    opening: str | None = Field(None, description="Part of the opening's name")
    date_from: date | None = None
    date_to: date | None = None


class PuzzleGameOut(Schema):
    """The game a puzzle comes from, to show and link to."""

    id: int
    white: str
    black: str
    date_pgn: str
    eco: str
    opening: str
    user_color: str


class PuzzleOut(Schema):
    id: int
    card_id: int
    game: PuzzleGameOut
    ply: int
    kind: PuzzleKind
    fen: str  # the position, with you to move
    last_move_uci: str  # the opponent's move that led to it ("" at the start)
    solution: list[str]  # your moves and the replies, in UCI
    themes: list[str]
    win_swing: float
    due_at: datetime

    @staticmethod
    def resolve_card_id(puzzle: Puzzle) -> int:
        return puzzle.card.pk

    @staticmethod
    def resolve_due_at(puzzle: Puzzle) -> datetime:
        return puzzle.card.due_at


class NextPuzzleOut(Schema):
    puzzle: PuzzleOut | None  # None when nothing is due
    due: int  # how many are due now, with the filters


class ReviewIn(Schema):
    card_id: int
    correct: bool  # solved without a wrong move
    elapsed_ms: int = Field(ge=0, le=24 * 60 * 60 * 1000)


class ReviewOut(Schema):
    id: int
    rating: ReviewLog.Rating  # 1 Again, 2 Hard, 3 Good, 4 Easy
    correct: bool
    next_due_at: datetime

    @staticmethod
    def resolve_next_due_at(log: ReviewLog) -> datetime:
        return log.card.due_at


class RatingIn(Schema):
    rating: ReviewLog.Rating


class WeekStatsOut(Schema):
    week: date
    reviews: int
    solved: int


class TrainingStatsOut(Schema):
    puzzles: int
    due_now: int
    due_today: int
    reviewed_today: int
    weeks: list[WeekStatsOut]
