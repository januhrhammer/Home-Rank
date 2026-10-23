"""Linking accounts on chess sites and syncing their games.

start_sync queues a sync; run_sync, which the background job calls, fetches the account's new
games and stores them like a file import does (games.services.store_games). See ADR 0011.
"""

import io
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus

import httpx
import structlog
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from procrastinate.contrib.django import app
from procrastinate.contrib.django.models import ProcrastinateJob

from homerank.accounts.models import User
from homerank.accounts.services import set_player_names
from homerank.chesslib.pgn import PgnError, PgnGame, read_pgn
from homerank.core.errors import DomainError
from homerank.games.models import Game
from homerank.games.services import NewGame, new_game, store_games
from homerank.sync import chesscom, lichess
from homerank.sync.http import PlayerNotFoundError, RateLimitedError, RemoteGame, new_client
from homerank.sync.models import LinkedAccount, SyncRun

logger = structlog.get_logger(__name__)

SOURCE_CODE_URL = "https://github.com/januhrhammer/Home-Rank"
# Games stored per database transaction; the progress and the cursor move on after each batch.
SYNC_BATCH_SIZE = 500
# Only the first problems of a sync are kept, like for file imports.
MAX_ERRORS_KEPT = 50
# Problems that end a sync without being a bug: they are recorded, not raised to the worker.
EXPECTED_ERRORS = (PlayerNotFoundError, RateLimitedError, httpx.HTTPError)


class AccountTakenError(DomainError):
    status = HTTPStatus.CONFLICT

    def __init__(self, account: LinkedAccount) -> None:
        platform = account.get_platform_display()
        self.detail = f'You have already linked the {platform} account "{account.username}".'
        super().__init__(self.detail)


def link_account(*, user: User, platform: str, username: str) -> LinkedAccount:
    """Link the account, add its username to the user's player names, and sync it."""
    account = LinkedAccount(user=user, platform=platform, username=username)
    with transaction.atomic():
        try:
            with transaction.atomic():  # a savepoint, so a failed insert doesn't end the request
                account.save()
        except IntegrityError as error:  # linked already, maybe with other upper/lower case
            raise AccountTakenError(account) from error
        # Synced games get the user's side from the player names (ADR 0009); this also finds
        # the user's side in games imported from files before. Unchanged if the name is there.
        set_player_names(user=user, names=[*user.player_names, username])
        start_sync(account)
    logger.info("Account linked", account_id=account.pk, platform=platform)
    return account


def unlink_account(account: LinkedAccount) -> None:
    """Forget the account and its syncs. Its games stay, as do the user's player names."""
    account.delete()


def start_sync(account: LinkedAccount) -> SyncRun:
    """Queue a sync of the account, unless one is queued or running already: that one is
    returned instead."""
    with transaction.atomic():
        # Locks the account's row, so two quick clicks on "sync now" don't queue two syncs.
        LinkedAccount.objects.select_for_update().get(pk=account.pk)
        if active := _active_run(account):
            return active
        run = SyncRun.objects.create(account=account)
        # The lock is the one the user's imports take (games.services.start_import), so two
        # jobs never store the same user's games at the same time.
        task = app.configure_task(
            "homerank.sync.tasks.sync_account", lock=f"user-{account.user_id}", queue="sync"
        )
        run.job_id = task.defer(sync_run_id=run.pk)
        run.save(update_fields=["job_id"])
    logger.info("Sync queued", account_id=account.pk, sync_run_id=run.pk)
    return run


def _active_run(account: LinkedAccount) -> SyncRun | None:
    """The account's queued or running sync. A run whose job is gone, e.g. because the worker
    was killed during the sync, is marked failed instead, so it doesn't block later syncs."""
    for run in account.runs.filter(status__in=[SyncRun.Status.QUEUED, SyncRun.Status.RUNNING]):
        job_alive = ProcrastinateJob.objects.filter(
            id=run.job_id, status__in=["todo", "doing"]
        ).exists()
        if job_alive:
            return run
        run.status = SyncRun.Status.FAILED
        run.errors.append({"game": None, "reason": "The sync stopped unexpectedly."})
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "errors", "finished_at"])
    return None


def user_agent() -> str:
    """Who is asking, as both sites want to know; with the operator's contact if set."""
    agent = f"Home-Rank (+{SOURCE_CODE_URL})"
    return f"{agent} {settings.SYNC_CONTACT}" if settings.SYNC_CONTACT else agent


def run_sync(*, sync_run_id: int) -> None:
    """Fetch and store the account's new games. Called by the job, not during a request."""
    run = SyncRun.objects.select_related("account__user").get(pk=sync_run_id)
    run.status = SyncRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])
    try:
        with new_client(user_agent=user_agent()) as client:
            if run.account.platform == LinkedAccount.Platform.LICHESS:
                _sync_lichess(run, client)
            else:
                _sync_chesscom(run, client)
    except Exception as error:
        # The job's boundary: record why the sync stopped. Expected problems, such as a
        # misspelt username or the site being down, need no stack trace in the worker's log.
        run.status = SyncRun.Status.FAILED
        run.errors.append({"game": None, "reason": f"The sync stopped: {error}"})
        if not isinstance(error, EXPECTED_ERRORS):
            raise
    else:
        run.status = SyncRun.Status.DONE
    finally:
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at", "errors"])
        logger.info(
            "Sync finished",
            sync_run_id=run.pk,
            status=run.status,
            imported=run.games_imported,
            duplicates=run.games_duplicate,
            failed=run.games_failed,
        )


def _sync_lichess(run: SyncRun, client: httpx.Client) -> None:
    """Lichess sends the games oldest first, from the cursor on; it moves with each batch."""
    account = run.account
    since = account.synced_until
    if since is not None:
        since += timedelta(milliseconds=1)  # the game at the cursor is stored already
    remote_games = lichess.games(client, account.username, since=since)
    for batch in _batches(remote_games):
        _store(run, batch, Game.Source.LICHESS, synced_until=batch[-1].played_at)


def _sync_chesscom(run: SyncRun, client: httpx.Client) -> None:
    """Chess.com has an archive per month: fetch the months from the cursor's on. A month
    that ended before this sync began is complete, and the cursor moves past it."""
    account = run.account
    this_month = timezone.now().astimezone(UTC).date().replace(day=1)
    first = account.synced_until.astimezone(UTC).date() if account.synced_until else None
    for month in chesscom.archives(client, account.username):
        if first is not None and month < first:
            continue
        remote_games = chesscom.month_games(client, account.username, month)
        for batch in _batches(remote_games):
            _store(run, batch, Game.Source.CHESSCOM, synced_until=None)
        if month < this_month:
            account.synced_until = _month_start(_next(month))
            account.save(update_fields=["synced_until"])


def _batches(remote_games: Iterable[RemoteGame]) -> Iterable[list[RemoteGame]]:
    batch: list[RemoteGame] = []
    for remote in remote_games:
        batch.append(remote)
        if len(batch) == SYNC_BATCH_SIZE:
            yield batch
            batch = []
    if batch:
        yield batch


def _store(
    run: SyncRun, batch: list[RemoteGame], source: str, *, synced_until: datetime | None
) -> None:
    """Store the batch's new games and update the progress (and the cursor, if given)."""
    account = run.account
    new_games: list[NewGame] = []
    for remote in batch:
        item = _parse(run, remote)
        if item is not None:
            new_games.append(new_game(account.user, item, source=source, source_id=remote.id))
    with transaction.atomic():
        stored = store_games(account.user, new_games)
        run.games_imported += stored.imported
        run.games_duplicate += stored.duplicate
        run.save(update_fields=["games_imported", "games_duplicate", "games_failed", "errors"])
        if synced_until is not None:
            account.synced_until = synced_until
            account.save(update_fields=["synced_until"])


def _parse(run: SyncRun, remote: RemoteGame) -> PgnGame | None:
    """The site's game, read like a PGN file's; None (and the problem noted) if it's broken."""
    items = list(read_pgn(io.BytesIO(remote.pgn.encode())))
    if len(items) == 1 and isinstance(items[0], PgnGame):
        return items[0]
    run.games_failed += 1
    reason = items[0].reason if items and isinstance(items[0], PgnError) else "No game found."
    if len(run.errors) < MAX_ERRORS_KEPT:
        run.errors.append({"game": remote.id, "reason": reason})
    return None


def _next(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


def _month_start(month: date) -> datetime:
    return datetime(month.year, month.month, 1, tzinfo=UTC)
