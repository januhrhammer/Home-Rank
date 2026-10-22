from http import HTTPStatus

from django.db.models import QuerySet
from django.http import HttpResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header
from ninja import File, Query, Router, Status, UploadedFile
from ninja.pagination import paginate

from homerank.accounts.auth import AuthenticatedRequest
from homerank.core.pagination import LimitOffset
from homerank.games import selectors, services
from homerank.games.models import Game, ImportRun
from homerank.games.schemas import GameFilters, GameListItem, GameOut, ImportOut

router = Router(tags=["games"])


@router.get("", response=list[GameListItem])
@paginate(LimitOffset)
def list_games(request: AuthenticatedRequest, filters: Query[GameFilters]) -> QuerySet[Game]:
    """Your games, filtered and sorted; the newest first unless sorted otherwise."""
    return selectors.games(user=request.user, filters=filters)


# The media type registered for PGN.
PGN_CONTENT_TYPE = "application/vnd.chess-pgn; charset=utf-8"


@router.get("/export")
def export_games(
    request: AuthenticatedRequest, filters: Query[GameFilters]
) -> StreamingHttpResponse:
    """Download the games the list would show, with the same filters, as one PGN file.

    For example ?collection=3 for a collection, or ?ids=1&ids=5 for a selection.
    """
    return StreamingHttpResponse(
        selectors.export_pgn(user=request.user, filters=filters),
        content_type=PGN_CONTENT_TYPE,
        headers={"Content-Disposition": content_disposition_header(True, "games.pgn")},
    )


@router.get("/{int:game_id}", response=GameOut)
def get_game(request: AuthenticatedRequest, game_id: int) -> Game:
    """One of your games, with its moves."""
    return selectors.game(user=request.user, game_id=game_id)


@router.get("/{int:game_id}/pgn")
def download_game(request: AuthenticatedRequest, game_id: int) -> HttpResponse:
    """Download one game as a PGN file."""
    game = selectors.game(user=request.user, game_id=game_id)
    return HttpResponse(
        game.pgn,
        content_type=PGN_CONTENT_TYPE,
        headers={"Content-Disposition": content_disposition_header(True, _file_name(game))},
    )


def _file_name(game: Game) -> str:
    """E.g. "Carlsen, Magnus - Anna 2024.03.05.pgn"; unknown parts are left out."""
    players = f"{game.white or 'Unknown'} - {game.black or 'Unknown'}"
    date = "" if game.date_pgn.startswith("?") else f" {game.date_pgn}"
    return f"{players}{date}.pgn".replace("/", "-").replace("\\", "-")


@router.post("/imports", response={HTTPStatus.ACCEPTED: ImportOut})
def create_import(request: AuthenticatedRequest, file: File[UploadedFile]) -> Status[ImportRun]:
    """Upload a PGN file to import.

    The import runs in the background: poll GET /games/imports/{id} for its progress.
    """
    run = services.start_import(user=request.user, file_name=file.name or "", chunks=file.chunks())
    return Status(HTTPStatus.ACCEPTED, run)


@router.get("/imports", response=list[ImportOut])
@paginate(LimitOffset)
def list_imports(request: AuthenticatedRequest) -> QuerySet[ImportRun]:
    """Your imports, the newest first."""
    return selectors.import_runs(user=request.user)


@router.get("/imports/{import_run_id}", response=ImportOut)
def get_import(request: AuthenticatedRequest, import_run_id: int) -> ImportRun:
    """One of your imports, with its progress."""
    return selectors.import_run(user=request.user, import_run_id=import_run_id)
