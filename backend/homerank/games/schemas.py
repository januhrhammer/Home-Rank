from datetime import date, datetime
from typing import Annotated, Literal

from ninja import Field, Schema
from pydantic import StringConstraints

from homerank.chesslib.headers import TimeClass
from homerank.chesslib.players import Side
from homerank.games.models import Game, ImportRun

GameSort = Literal[
    "date",
    "-date",
    "white",
    "-white",
    "black",
    "-black",
    "white_elo",
    "-white_elo",
    "black_elo",
    "-black_elo",
    "eco",
    "-eco",
    "imported_at",
    "-imported_at",
]


class ImportErrorOut(Schema):
    line: int | None  # where the game starts in the file; None if the whole import stopped
    reason: str


class ImportOut(Schema):
    """An import and its progress. The frontend polls it while it is queued or running."""

    id: int
    file_name: str
    status: ImportRun.Status
    file_size: int  # bytes
    bytes_read: int  # progress: bytes_read / file_size
    games_imported: int
    games_duplicate: int
    games_failed: int
    errors: list[ImportErrorOut]  # the first problems found
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class GameFilters(Schema):
    """Filters for the game list; all optional, and combined with AND."""

    player: str | None = Field(None, description="Part of White's or Black's name")
    color: Side | None = Field(None, description="The side you played")
    result: Literal["1-0", "0-1", "1/2-1/2", "*"] | None = None
    outcome: Literal["win", "draw", "loss"] | None = Field(
        None, description="The result from your side; only games in which you played"
    )
    date_from: date | None = None
    date_to: date | None = None
    eco: str | None = Field(
        None, pattern=r"^[A-Ea-e]\d{0,2}$", description="An ECO code or its start: B, B2, B23"
    )
    opening: str | None = Field(None, description="Part of the opening's name")
    source: Game.Source | None = None
    time_class: TimeClass | None = None
    tag: int | None = Field(None, description="Only games with this tag")
    collection: int | None = Field(None, description="Only games in this collection")
    import_run: int | None = Field(None, description="Only games from this import")
    ids: list[int] | None = Field(None, description="Only these games, e.g. a selection")
    sort: GameSort = Field("-date", description="A field to sort by; a leading - sorts downwards")


class NamedRef(Schema):
    """A collection or tag as other objects mention it."""

    id: int
    name: str


class GameListItem(Schema):
    """A game in the list: its headers and tags, without the moves."""

    id: int
    white: str
    black: str
    white_elo: int | None
    black_elo: int | None
    result: str
    date: date | None  # the earliest day date_pgn can mean
    date_pgn: str  # the date with its precision, e.g. "1960.??.??"
    event: str
    site: str
    eco: str
    opening: str
    time_control: str
    time_class: TimeClass
    user_color: Literal["white", "black", ""]
    ply_count: int
    source: Game.Source
    imported_at: datetime
    tags: list[NamedRef]


class GameOut(GameListItem):
    """A game with its moves: the PGN text exactly as imported."""

    pgn: str
    import_run_id: int | None
    collections: list[NamedRef]


# Names are trimmed; an empty one is refused.
CollectionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
TagName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class CollectionIn(Schema):
    name: CollectionName
    description: str = ""


class CollectionPatch(Schema):
    """The fields to change; those left out stay as they are."""

    name: CollectionName | None = None
    description: str | None = None


class CollectionOut(Schema):
    id: int
    name: str
    description: str
    game_count: int
    created_at: datetime


class TagIn(Schema):
    name: TagName


class TagOut(Schema):
    id: int
    name: str
    game_count: int


class GameIdsIn(Schema):
    game_ids: list[int] = Field(min_length=1, max_length=1000)
