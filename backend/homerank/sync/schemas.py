from datetime import datetime
from typing import Annotated

from ninja import Schema
from pydantic import StringConstraints

from homerank.sync.models import LinkedAccount, SyncRun

# What both sites allow in usernames: letters, digits, "_" and "-". It also keeps the name
# harmless inside the sites' URLs.
Username = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{2,50}$")
]


class SyncErrorOut(Schema):
    game: str | None  # the site's id of a broken game; None if the whole sync stopped
    reason: str


class SyncRunOut(Schema):
    """A sync and what it found. The frontend polls it while it is queued or running."""

    id: int
    status: SyncRun.Status
    games_imported: int
    games_duplicate: int
    games_failed: int
    errors: list[SyncErrorOut]  # the first problems found
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class LinkedAccountOut(Schema):
    id: int
    platform: LinkedAccount.Platform
    username: str
    enabled: bool  # synced on schedule; "sync now" works either way
    synced_until: datetime | None  # all games played before this are stored
    created_at: datetime
    last_run: SyncRunOut | None  # the newest sync

    @staticmethod
    def resolve_last_run(account: LinkedAccount) -> SyncRun | None:
        # selectors.accounts prefetches the newest run into latest_runs.
        runs: list[SyncRun] = account.latest_runs  # type: ignore[attr-defined]
        return runs[0] if runs else None


class LinkedAccountIn(Schema):
    platform: LinkedAccount.Platform
    username: Username


class LinkedAccountPatch(Schema):
    enabled: bool
