from datetime import date

from ninja import Field, Schema

from homerank.chesslib.players import Side
from homerank.repertoire.models import RepertoireMove
from homerank.repertoire.services import SEED_DEPTH, SEED_MIN_GAMES


class RepertoireIn(Schema):
    name: str = Field(min_length=1, max_length=100)
    color: Side


class RepertoirePatch(Schema):
    name: str = Field(min_length=1, max_length=100)


class RepertoireOut(Schema):
    id: int
    name: str
    color: Side
    move_count: int
    due: int  # cards due now


class MoveIn(Schema):
    fen: str = Field(max_length=100, description="The position the move is played from")
    move_uci: str = Field(max_length=5, examples=["e2e4"])


class MovePatch(Schema):
    comment: str = Field(max_length=2000)


class MoveOut(Schema):
    """A move from one position to the next. Positions are named by their hash, as a string:
    a move continues another when its from_position is the other's to_position."""

    id: int
    from_position: str
    from_fen: str
    move_uci: str
    move_san: str
    to_position: str
    comment: str
    card_id: int | None  # your own moves have a card; the opponent's don't

    @staticmethod
    def resolve_from_position(move: RepertoireMove) -> str:
        return str(move.from_zobrist)

    @staticmethod
    def resolve_to_position(move: RepertoireMove) -> str:
        return str(move.to_zobrist)

    @staticmethod
    def resolve_card_id(move: RepertoireMove) -> int | None:
        card = getattr(move, "card", None)
        return card.pk if card is not None else None


class RemovedOut(Schema):
    removed: int  # the move and those only it led to


class PgnIn(Schema):
    pgn: str = Field(max_length=1_000_000)


class PgnImportOut(Schema):
    moves_added: int
    games_read: int
    games_skipped: int  # unreadable, or not from the starting position


class SeedIn(Schema):
    depth: int = Field(SEED_DEPTH, ge=1, le=30, description="Plies from the start")
    min_games: int = Field(
        SEED_MIN_GAMES, ge=1, le=1000, description="Games an opponent's reply needs"
    )


class SeedOut(Schema):
    moves_added: int


class GapOut(Schema):
    fen: str
    move_uci: str
    move_san: str
    by_user: bool  # your own move left the repertoire; else the opponent's isn't covered
    games: int
    game_ids: list[int]  # the latest games, newest first
    last_played: date | None


class DrillStepOut(Schema):
    move_id: int
    fen: str
    move_uci: str
    move_san: str
    comment: str
    card_id: int | None  # None: the opponent's move, played for you
    due: bool
    other_moves: list[str]  # your other moves here, in UCI: not wrong, but not this card's


class DueDrillOut(Schema):
    step: DrillStepOut | None  # None when nothing is due
    last_move_uci: str  # the move that led to the position, "" at the start
    due: int
