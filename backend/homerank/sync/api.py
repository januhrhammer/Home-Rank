from http import HTTPStatus

from django.db.models import QuerySet
from ninja import Router, Status
from ninja.pagination import paginate

from homerank.accounts.auth import AuthenticatedRequest
from homerank.core.pagination import LimitOffset
from homerank.sync import selectors, services
from homerank.sync.models import LinkedAccount, SyncRun
from homerank.sync.schemas import LinkedAccountIn, LinkedAccountOut, LinkedAccountPatch, SyncRunOut

router = Router(tags=["sync"])


@router.get("/accounts", response=list[LinkedAccountOut])
@paginate(LimitOffset)
def list_accounts(request: AuthenticatedRequest) -> QuerySet[LinkedAccount]:
    """Your accounts on Lichess and Chess.com, each with its newest sync."""
    return selectors.accounts(user=request.user)


@router.post("/accounts", response={HTTPStatus.CREATED: LinkedAccountOut})
def link_account(request: AuthenticatedRequest, data: LinkedAccountIn) -> Status[LinkedAccount]:
    """Link an account and sync its games; 409 if it is linked already.

    The username is added to your player names, so your side is known in its games.
    """
    account = services.link_account(
        user=request.user, platform=data.platform, username=data.username
    )
    return Status(HTTPStatus.CREATED, _account(request, account.pk))


@router.get("/accounts/{int:account_id}", response=LinkedAccountOut)
def get_account(request: AuthenticatedRequest, account_id: int) -> LinkedAccount:
    return _account(request, account_id)


@router.patch("/accounts/{int:account_id}", response=LinkedAccountOut)
def update_account(
    request: AuthenticatedRequest, account_id: int, data: LinkedAccountPatch
) -> LinkedAccount:
    """Turn the scheduled sync of an account on or off."""
    account = _account(request, account_id)
    account.enabled = data.enabled
    account.save(update_fields=["enabled"])
    return _account(request, account_id)


@router.delete("/accounts/{int:account_id}", response={HTTPStatus.NO_CONTENT: None})
def unlink_account(request: AuthenticatedRequest, account_id: int) -> Status[None]:
    """Unlink an account. Its games stay in your database."""
    services.unlink_account(_account(request, account_id))
    return Status(HTTPStatus.NO_CONTENT, None)


@router.post("/accounts/{int:account_id}/sync", response={HTTPStatus.ACCEPTED: SyncRunOut})
def sync_account(request: AuthenticatedRequest, account_id: int) -> Status[SyncRun]:
    """Sync an account now. If a sync is queued or running already, that one is returned.

    The sync runs in the background: poll GET /sync/accounts/{id} for its progress.
    """
    run = services.start_sync(_account(request, account_id))
    return Status(HTTPStatus.ACCEPTED, run)


def _account(request: AuthenticatedRequest, account_id: int) -> LinkedAccount:
    return selectors.account(user=request.user, account_id=account_id)
