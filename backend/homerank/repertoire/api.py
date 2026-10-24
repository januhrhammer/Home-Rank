from http import HTTPStatus

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from ninja import File, Query, Router, Status, UploadedFile

from homerank.accounts.auth import AuthenticatedRequest
from homerank.repertoire import selectors, services
from homerank.repertoire.models import Repertoire, RepertoireLine, RepertoireMove
from homerank.repertoire.schemas import (
    ConflictOut,
    DrillStepOut,
    DueDrillOut,
    GapOut,
    LineIn,
    LineOrderIn,
    LineOut,
    MoveIn,
    MoveOut,
    MovePatch,
    PgnImportOut,
    RemovedOut,
    RepertoireIn,
    RepertoireOut,
    RepertoirePatch,
    SeedIn,
    SeedOut,
)
from homerank.repertoire.selectors import Conflict, DrillStep, DueDrill, Gap
from homerank.repertoire.services import PgnImport

router = Router(tags=["repertoires"])


@router.get("", response=list[RepertoireOut])
def list_repertoires(request: AuthenticatedRequest) -> QuerySet[Repertoire]:
    """Your repertoires by name."""
    return selectors.repertoires(user=request.user)


@router.post("", response={HTTPStatus.CREATED: RepertoireOut})
def create_repertoire(request: AuthenticatedRequest, data: RepertoireIn) -> Status[Repertoire]:
    """Create an empty repertoire; 409 if you already have one with that name."""
    repertoire = services.create_repertoire(user=request.user, name=data.name, color=data.color)
    return Status(HTTPStatus.CREATED, _listed(request, repertoire.pk))


@router.get("/{int:repertoire_id}", response=RepertoireOut)
def get_repertoire(request: AuthenticatedRequest, repertoire_id: int) -> Repertoire:
    return _listed(request, repertoire_id)


@router.patch("/{int:repertoire_id}", response=RepertoireOut)
def rename_repertoire(
    request: AuthenticatedRequest, repertoire_id: int, data: RepertoirePatch
) -> Repertoire:
    """Rename a repertoire. Its colour can't change."""
    services.rename_repertoire(_repertoire(request, repertoire_id), name=data.name)
    return _listed(request, repertoire_id)


@router.delete("/{int:repertoire_id}", response={HTTPStatus.NO_CONTENT: None})
def delete_repertoire(request: AuthenticatedRequest, repertoire_id: int) -> Status[None]:
    """Delete a repertoire with its moves and their training history."""
    _repertoire(request, repertoire_id).delete()
    return Status(HTTPStatus.NO_CONTENT, None)


# ---------------------------------------------------------------- lines


@router.get("/{int:repertoire_id}/lines", response=list[LineOut])
def list_lines(request: AuthenticatedRequest, repertoire_id: int) -> QuerySet[RepertoireLine]:
    """The repertoire's lines in their order. A new repertoire has one, "Main line"."""
    return selectors.lines(_repertoire(request, repertoire_id))


@router.post("/{int:repertoire_id}/lines", response={HTTPStatus.CREATED: LineOut})
def create_line(
    request: AuthenticatedRequest, repertoire_id: int, data: LineIn
) -> Status[RepertoireLine]:
    """Add an empty line after the others; 409 if the repertoire has one with that name."""
    line = services.create_line(_repertoire(request, repertoire_id), name=data.name)
    return Status(HTTPStatus.CREATED, _listed_line(request, repertoire_id, line.pk))


@router.put("/{int:repertoire_id}/lines/order", response=list[LineOut])
def reorder_lines(
    request: AuthenticatedRequest, repertoire_id: int, data: LineOrderIn
) -> QuerySet[RepertoireLine]:
    """Put the lines in this order, naming each of them once."""
    repertoire = _repertoire(request, repertoire_id)
    services.reorder_lines(repertoire, line_ids=data.line_ids)
    return selectors.lines(repertoire)


@router.patch("/{int:repertoire_id}/lines/{int:line_id}", response=LineOut)
def rename_line(
    request: AuthenticatedRequest, repertoire_id: int, line_id: int, data: LineIn
) -> RepertoireLine:
    services.rename_line(_line(request, repertoire_id, line_id), name=data.name)
    return _listed_line(request, repertoire_id, line_id)


@router.delete("/{int:repertoire_id}/lines/{int:line_id}", response=RemovedOut)
def delete_line(request: AuthenticatedRequest, repertoire_id: int, line_id: int) -> dict[str, int]:
    """Delete a line, and the moves no other line has (with their training history); 409 for
    the repertoire's last line."""
    return {"removed": services.delete_line(_line(request, repertoire_id, line_id))}


@router.get("/{int:repertoire_id}/conflicts", response=list[ConflictOut])
def conflicts(request: AuthenticatedRequest, repertoire_id: int) -> list[Conflict]:
    """Positions where lines of the repertoire play different moves of yours."""
    return selectors.conflicts(_repertoire(request, repertoire_id))


# ---------------------------------------------------------------- moves


@router.get("/{int:repertoire_id}/moves", response=list[MoveOut])
def list_moves(request: AuthenticatedRequest, repertoire_id: int) -> QuerySet[RepertoireMove]:
    """All of the repertoire's moves, in the order they were added, with their lines. The tree
    is drawn from the starting position by following each move's to_position."""
    return (
        selectors.moves(_repertoire(request, repertoire_id))
        .select_related("card")
        .prefetch_related("lines")
    )


@router.post("/{int:repertoire_id}/moves", response={HTTPStatus.CREATED: MoveOut})
def add_move(
    request: AuthenticatedRequest, repertoire_id: int, data: MoveIn
) -> Status[RepertoireMove]:
    """Add a move to a line, in a position the line reaches. A move the line has is returned;
    one another line has joins this line too."""
    repertoire = _repertoire(request, repertoire_id)
    line = _line(request, repertoire_id, data.line_id) if data.line_id is not None else None
    move = services.add_move(repertoire, fen=data.fen, move_uci=data.move_uci, line=line)
    return Status(HTTPStatus.CREATED, _move(request, repertoire_id, move.pk))


@router.patch("/{int:repertoire_id}/moves/{int:move_id}", response=MoveOut)
def comment_move(
    request: AuthenticatedRequest, repertoire_id: int, move_id: int, data: MovePatch
) -> RepertoireMove:
    services.set_comment(_move(request, repertoire_id, move_id), comment=data.comment)
    return _move(request, repertoire_id, move_id)


@router.delete("/{int:repertoire_id}/moves/{int:move_id}", response=RemovedOut)
def remove_move(
    request: AuthenticatedRequest,
    repertoire_id: int,
    move_id: int,
    line_id: Query[int | None] = None,
) -> dict[str, int]:
    """Take a move out of a line, or without line_id out of every line, with the moves the
    line reached only through it. Moves left in no line are deleted."""
    move = _move(request, repertoire_id, move_id)
    line = _line(request, repertoire_id, line_id) if line_id is not None else None
    return {"removed": services.remove_move(move, line=line)}


@router.post("/{int:repertoire_id}/import", response=PgnImportOut)
def import_pgn(
    request: AuthenticatedRequest,
    repertoire_id: int,
    file: File[UploadedFile],
    line_id: Query[int | None] = None,
    chapters: Query[bool] = False,
) -> PgnImport:
    """Upload a PGN file (at most 20 MB) and add its moves, variations and comments included:
    to a line (default: the first), or with chapters=true each game as a new line, named after
    its ChapterName or Event. Games that don't start from the starting position are skipped."""
    repertoire = _repertoire(request, repertoire_id)
    if chapters:
        return services.import_pgn_chapters(repertoire, lines=file)
    line = _line(request, repertoire_id, line_id) if line_id is not None else None
    return services.import_pgn(repertoire, lines=file, into=line)


@router.post("/{int:repertoire_id}/seed", response=SeedOut)
def seed(request: AuthenticatedRequest, repertoire_id: int, data: SeedIn) -> dict[str, int]:
    """Add to a line what you play in your games with this colour: your most played moves and
    the replies you met in at least min_games games. Moves already there stay."""
    repertoire = _repertoire(request, repertoire_id)
    line = _line(request, repertoire_id, data.line_id) if data.line_id is not None else None
    added = services.seed_from_games(
        repertoire, depth=data.depth, min_games=data.min_games, into=line
    )
    return {"moves_added": added}


@router.get("/{int:repertoire_id}/gaps", response=list[GapOut])
def gaps(request: AuthenticatedRequest, repertoire_id: int) -> list[Gap]:
    """Where your games left the repertoire, most frequent first."""
    return selectors.gaps(_repertoire(request, repertoire_id))


# ---------------------------------------------------------------- drill


@router.get("/{int:repertoire_id}/drill/next", response=DueDrillOut)
def next_card(
    request: AuthenticatedRequest, repertoire_id: int, line: Query[list[int] | None] = None
) -> DueDrill:
    """The card due longest, of the repertoire or of the lines given (line=1&line=2). Answer it
    with POST /training/reviews."""
    repertoire = _repertoire(request, repertoire_id)
    return selectors.next_due(repertoire, line_ids=_line_ids(request, repertoire_id, line))


@router.get("/{int:repertoire_id}/drill/line", response=list[DrillStepOut])
def drill_line(
    request: AuthenticatedRequest,
    repertoire_id: int,
    through: Query[int | None] = None,
    line: Query[list[int] | None] = None,
) -> list[DrillStep]:
    """A line from the start to the end of the repertoire, or of the lines given, through the
    move with the id given, or else through the card due longest. Answer each of your moves
    with POST /training/reviews."""
    repertoire = _repertoire(request, repertoire_id)
    move = _move(request, repertoire_id, through) if through is not None else None
    line_ids = _line_ids(request, repertoire_id, line)
    return selectors.drill_line(repertoire, through=move, line_ids=line_ids)


def _repertoire(request: AuthenticatedRequest, repertoire_id: int) -> Repertoire:
    return selectors.repertoire(user=request.user, repertoire_id=repertoire_id)


def _listed(request: AuthenticatedRequest, repertoire_id: int) -> Repertoire:
    """The repertoire with its counts, as the list shows it."""
    return get_object_or_404(selectors.repertoires(user=request.user), pk=repertoire_id)


def _move(request: AuthenticatedRequest, repertoire_id: int, move_id: int) -> RepertoireMove:
    return selectors.move(user=request.user, repertoire_id=repertoire_id, move_id=move_id)


def _line(request: AuthenticatedRequest, repertoire_id: int, line_id: int) -> RepertoireLine:
    return selectors.line(user=request.user, repertoire_id=repertoire_id, line_id=line_id)


def _listed_line(request: AuthenticatedRequest, repertoire_id: int, line_id: int) -> RepertoireLine:
    """The line with its count, as the list shows it."""
    return get_object_or_404(selectors.lines(_repertoire(request, repertoire_id)), pk=line_id)


def _line_ids(
    request: AuthenticatedRequest, repertoire_id: int, line_ids: list[int] | None
) -> list[int] | None:
    """The lines asked for, each checked to be one of the repertoire's (404 otherwise)."""
    return [_line(request, repertoire_id, pk).pk for pk in line_ids] if line_ids else None
