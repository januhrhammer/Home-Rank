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
    line_count: int
    move_count: int
    due: int  # cards due now


class LineIn(Schema):
    name: str = Field(min_length=1, max_length=100)


class LineOut(Schema):
    id: int
    name: str
    position: int  # the lines' order in their repertoire
    move_count: int


class LineOrderIn(Schema):
    line_ids: list[int] = Field(description="Each of the repertoire's lines once, in the new order")


class ConflictChoiceOut(Schema):
    move_uci: str
    move_san: str
    lines: list[str]  # the lines that play it, in their order


class ConflictOut(Schema):
    """A position where lines play different moves of yours."""

    fen: str
    choices: list[ConflictChoiceOut]


class MoveIn(Schema):
    fen: str = Field(max_length=100, description="The position the move is played from")
    move_uci: str = Field(max_length=5, examples=["e2e4"])
    line_id: int | None = Field(
        None, description="The line to add it to; default: the first that reaches the position"
    )


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
    line_ids: list[int]  # the lines it belongs to, at least one

    @staticmethod
    def resolve_line_ids(move: RepertoireMove) -> list[int]:
        return sorted(line.pk for line in move.lines.all())

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
    removed: int  # moves taken out: the move and those only it led to, or a line's own moves


class PgnImportOut(Schema):
    moves_added: int
    games_read: int
    games_skipped: int  # unreadable, or not from the starting position
    lines_created: int  # one per game when imported as chapters


class SeedIn(Schema):
    depth: int = Field(SEED_DEPTH, ge=1, le=30, description="Plies from the start")
    min_games: int = Field(
        SEED_MIN_GAMES, ge=1, le=1000, description="Games an opponent's reply needs"
    )
    line_id: int | None = Field(None, description="The line to add to; default: the first")


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
