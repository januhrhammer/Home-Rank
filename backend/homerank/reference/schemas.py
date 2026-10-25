from datetime import date, datetime

from ninja import Field, Schema

from homerank.reference.models import ReferenceDatabase, ReferenceGame
from homerank.reference.openings import shown_opening


class ReferenceDatabaseOut(Schema):
    id: int
    name: str
    description: str
    depth: int  # plies indexed per game
    status: ReferenceDatabase.DatabaseStatus
    game_count: int
    imported_at: datetime | None


class ReferenceGameFilters(Schema):
    player: str | None = Field(None, description="Part of White's or Black's name")
    eco: str | None = Field(None, pattern=r"^[A-Ea-e]\d{0,2}$")
    result: str | None = Field(None, pattern=r"^(1-0|0-1|1/2-1/2|\*)$")
    date_from: date | None = None
    date_to: date | None = None
    min_rating: int | None = Field(None, description="Both players rated at least this")


class ReferenceGameItem(Schema):
    id: int
    white: str
    black: str
    white_elo: int | None
    black_elo: int | None
    result: str
    date_pgn: str
    event: str
    site: str
    eco: str  # these two as shown: named by the game's positions, else its headers (ADR 0021)
    opening: str
    ply_count: int

    @staticmethod
    def resolve_eco(game: ReferenceGame) -> str:
        return shown_opening(game).eco

    @staticmethod
    def resolve_opening(game: ReferenceGame) -> str:
        return shown_opening(game).name


class ReferenceGameOut(ReferenceGameItem):
    pgn: str  # rebuilt from the stored moves


class CopyIn(Schema):
    collection: int | None = Field(None, description="Also add the copy to this collection")


class CopyOut(Schema):
    game_id: int  # your game: the new copy, or the one you had already
    created: bool
