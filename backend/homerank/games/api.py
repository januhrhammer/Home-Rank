from http import HTTPStatus

from django.db.models import QuerySet
from ninja import File, Router, Status, UploadedFile
from ninja.pagination import paginate

from homerank.accounts.auth import AuthenticatedRequest
from homerank.core.pagination import LimitOffset
from homerank.games import selectors, services
from homerank.games.models import ImportRun
from homerank.games.schemas import ImportOut

router = Router(tags=["games"])


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
