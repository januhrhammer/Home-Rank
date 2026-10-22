from datetime import datetime

from ninja import Schema

from homerank.games.models import ImportRun


class ImportErrorOut(Schema):
    line: int | None  # where the game starts in the file; None if the whole import stopped
    reason: str


class ImportOut(Schema):
    """An import and its progress. The frontend polls it while it is queued or running."""

    id: int
    file_name: str
    status: ImportRun.Status
    file_size: int  # bytes
    bytes_read: int  # progress: bytes_read / file_size
    games_imported: int
    games_duplicate: int
    games_failed: int
    errors: list[ImportErrorOut]  # the first problems found
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
