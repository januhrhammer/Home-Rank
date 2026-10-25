from datetime import datetime

from ninja import Field, Schema

from homerank.chesslib.players import Side
from homerank.novelty.models import RatingKind, SearchStatus
from homerank.novelty.services import MAIA_HIGH, MAIA_LOW


class SearchIn(Schema):
    fen: str = Field(max_length=100, description="The position to search from")
    moves: list[str] = Field(
        default_factory=list, max_length=200, description="The moves (UCI) that led there"
    )
    label: str = Field("", max_length=200, examples=["Smith-Morra, after 9.Rd1 e5"])
    side: Side = Field(description="The side you prepare for")
    rating: int = Field(ge=0, le=3500, description="The opponent's rating, as you know it")
    rating_kind: RatingKind = RatingKind.FIDE
    elo: int | None = Field(
        None,
        ge=MAIA_LOW,
        le=MAIA_HIGH,
        description="The Lichess rating Maia plays at; default: converted from rating",
    )
    budget_cp: int = Field(150, ge=0, le=500, description="How far below 0 your moves may go")
    limit_minutes: int = Field(60, ge=1, le=12 * 60)


class SearchOut(Schema):
    id: int
    start_fen: str
    start_moves: list[str]
    start_label: str
    side: Side
    rating: int
    rating_kind: RatingKind
    elo: int
    budget_cp: int
    limit_minutes: int
    status: SearchStatus
    own_moves: int  # how many of your moves deep the last finished step looked
    error: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RefutationStepOut(Schema):
    san: str
    uci: str
    found: float  # how likely the opponent finds this move or one nearly as good, 0 to 1


class TryOut(Schema):
    rank: int
    line: list[str]  # moves (UCI) from the search's start to the try's position
    uci: str
    san: str
    cp: int  # for you, checked at depth 24
    practical: float  # your expected score against the opponent, 0 to 1
    best_san: str
    best_practical: float
    reach: float
    refutation: list[RefutationStepOut]
    reference_games: int | None


class SearchDetailOut(SearchOut):
    tries: list[TryOut]


class RatingOut(Schema):
    elo: int  # the Lichess rating Maia would play at
