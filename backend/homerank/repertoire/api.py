from http import HTTPStatus

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from ninja import File, Query, Router, Status, UploadedFile

from homerank.accounts.auth import AuthenticatedRequest
from homerank.repertoire import selectors, services
from homerank.repertoire.models import Repertoire, RepertoireMove
from homerank.repertoire.schemas import (
    DrillStepOut,
    DueDrillOut,
    GapOut,
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
from homerank.repertoire.selectors import DrillStep, DueDrill, Gap
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


# ---------------------------------------------------------------- moves


@router.get("/{int:repertoire_id}/moves", response=list[MoveOut])
def list_moves(request: AuthenticatedRequest, repertoire_id: int) -> QuerySet[RepertoireMove]:
    """All of the repertoire's moves, in the order they were added. The tree is drawn from
    the starting position by following each move's to_position."""
    return selectors.moves(_repertoire(request, repertoire_id)).select_related("card")


@router.post("/{int:repertoire_id}/moves", response={HTTPStatus.CREATED: MoveOut})
def add_move(
    request: AuthenticatedRequest, repertoire_id: int, data: MoveIn
) -> Status[RepertoireMove]:
    """Add a move in a position the repertoire reaches; a move it already has is returned."""
    repertoire = _repertoire(request, repertoire_id)
    move = services.add_move(repertoire, fen=data.fen, move_uci=data.move_uci)
    return Status(HTTPStatus.CREATED, _move(request, repertoire_id, move.pk))


@router.patch("/{int:repertoire_id}/moves/{int:move_id}", response=MoveOut)
def comment_move(
    request: AuthenticatedRequest, repertoire_id: int, move_id: int, data: MovePatch
) -> RepertoireMove:
    services.set_comment(_move(request, repertoire_id, move_id), comment=data.comment)
    return _move(request, repertoire_id, move_id)


@router.delete("/{int:repertoire_id}/moves/{int:move_id}", response=RemovedOut)
def remove_move(request: AuthenticatedRequest, repertoire_id: int, move_id: int) -> dict[str, int]:
    """Remove a move and the moves only it led to."""
    return {"removed": services.remove_move(_move(request, repertoire_id, move_id))}


@router.post("/{int:repertoire_id}/import", response=PgnImportOut)
def import_pgn(
    request: AuthenticatedRequest, repertoire_id: int, file: File[UploadedFile]
) -> PgnImport:
    """Upload a PGN file (at most 20 MB) and add its moves, variations and comments included.
    Games that don't start from the starting position are skipped."""
    return services.import_pgn(_repertoire(request, repertoire_id), lines=file)


@router.post("/{int:repertoire_id}/seed", response=SeedOut)
def seed(request: AuthenticatedRequest, repertoire_id: int, data: SeedIn) -> dict[str, int]:
    """Add what you play in your games with this colour: your most played moves and the
    replies you met in at least min_games games. Moves already there stay."""
    repertoire = _repertoire(request, repertoire_id)
    added = services.seed_from_games(repertoire, depth=data.depth, min_games=data.min_games)
    return {"moves_added": added}


@router.get("/{int:repertoire_id}/gaps", response=list[GapOut])
def gaps(request: AuthenticatedRequest, repertoire_id: int) -> list[Gap]:
    """Where your games left the repertoire, most frequent first."""
    return selectors.gaps(_repertoire(request, repertoire_id))


# ---------------------------------------------------------------- drill


@router.get("/{int:repertoire_id}/drill/next", response=DueDrillOut)
def next_card(request: AuthenticatedRequest, repertoire_id: int) -> DueDrill:
    """The card due longest. Answer it with POST /training/reviews."""
    return selectors.next_due(_repertoire(request, repertoire_id))


@router.get("/{int:repertoire_id}/drill/line", response=list[DrillStepOut])
def drill_line(
    request: AuthenticatedRequest, repertoire_id: int, through: Query[int | None] = None
) -> list[DrillStep]:
    """A line from the start to the end of the repertoire, through the move with the id given,
    or else through the card due longest. Answer each of your moves with POST
    /training/reviews."""
    repertoire = _repertoire(request, repertoire_id)
    move = _move(request, repertoire_id, through) if through is not None else None
    return selectors.drill_line(repertoire, through=move)


def _repertoire(request: AuthenticatedRequest, repertoire_id: int) -> Repertoire:
    return selectors.repertoire(user=request.user, repertoire_id=repertoire_id)


def _listed(request: AuthenticatedRequest, repertoire_id: int) -> Repertoire:
    """The repertoire with its counts, as the list shows it."""
    return get_object_or_404(selectors.repertoires(user=request.user), pk=repertoire_id)


def _move(request: AuthenticatedRequest, repertoire_id: int, move_id: int) -> RepertoireMove:
    return selectors.move(user=request.user, repertoire_id=repertoire_id, move_id=move_id)
