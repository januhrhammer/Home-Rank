from datetime import date

from ninja import Field, Schema

from homerank.chesslib.headers import TimeClass
from homerank.chesslib.players import Side
from homerank.games.models import Game
from homerank.games.schemas import GameListItem
from homerank.reference.schemas import ReferenceGameItem


class PositionQuery(Schema):
    fen: str = Field(description="The position in FEN, e.g. from the board or the viewer")


class MyGamesQuery(PositionQuery):
    color: Side | None = Field(None, description="The side you played")
    time_class: TimeClass | None = None
    source: Game.Source | None = None
    date_from: date | None = None
    date_to: date | None = None


class ReferenceQuery(PositionQuery):
    min_rating: int | None = Field(None, description="Both players rated at least this")
    max_rating: int | None = Field(None, description="Both players rated at most this")
    date_from: date | None = None
    date_to: date | None = None


class PageQuery(Schema):
    page: int = Field(1, ge=1)


class MoveStatsOut(Schema):
    uci: str
    san: str
    games: int
    white: int  # games White won after the move
    draws: int
    black: int
    average_rating: float | None  # your opponents' in your games; both players' in a reference
    last_played: date | None  # a reference database knows the year (January 1st)


class OpeningOut(Schema):
    eco: str
    name: str


class ExplorerOut(Schema):
    games: int
    moves: list[MoveStatsOut]
    filtered: bool  # false if the filters couldn't apply (a very common position)
    opening: OpeningOut | None  # the position's name in Lichess's opening list, if it has one


class MyFoundGame(GameListItem):
    ply: int  # where the game reached the position


class MySearchOut(Schema):
    items: list[MyFoundGame]
    total: int


class ReferenceFoundGame(ReferenceGameItem):
    ply: int


class ReferenceSearchOut(Schema):
    items: list[ReferenceFoundGame]
    total: int
    too_common: bool  # in so many games that they aren't listed: narrow the position down
