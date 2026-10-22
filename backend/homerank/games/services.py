"""Importing games from PGN files.

start_import saves an uploaded file and queues its import; run_import, which the background job
calls, reads the file and stores its games, their positions and the progress.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import BinaryIO

import chess.pgn
import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from procrastinate.contrib.django import app

from homerank.accounts.models import User
from homerank.chesslib.dedup import dedup_hash
from homerank.chesslib.headers import read_headers
from homerank.chesslib.pgn import PgnError, PgnGame, read_pgn
from homerank.chesslib.players import user_side
from homerank.chesslib.positions import as_bigint, positions
from homerank.core.errors import DomainError
from homerank.games.models import Game, GamePosition, ImportRun

logger = structlog.get_logger(__name__)

# Games stored per database transaction; progress is updated after each batch.
IMPORT_BATCH_SIZE = 500
# Only the first problems of a file are kept: a file of broken games needs no thousand messages.
MAX_ERRORS_KEPT = 50


class ImportTooLargeError(DomainError):
    status = HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    def __init__(self) -> None:
        megabytes = settings.IMPORT_MAX_BYTES // (1024 * 1024)
        self.detail = f"PGN files can be at most {megabytes} MB."
        super().__init__(self.detail)


class UnsupportedFileError(DomainError):
    status = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    detail = "Only PGN files (.pgn) can be imported."


def import_path(run: ImportRun) -> Path:
    """Where an import's file waits for its job."""
    return Path(settings.DATA_DIR) / "imports" / f"{run.pk}.pgn"


def start_import(*, user: User, file_name: str, chunks: Iterable[bytes]) -> ImportRun:
    """Save an uploaded PGN file, arriving in chunks, and queue the job that imports it."""
    if not file_name.lower().endswith(".pgn"):
        raise UnsupportedFileError
    with transaction.atomic():
        run = ImportRun.objects.create(user=user, file_name=file_name[:255], file_size=0)
        path = import_path(run)
        try:
            run.file_size = _save(chunks, path)
            # The job is queued in this transaction: it exists if and only if the run does. The
            # lock makes a user's imports run one after another, so two of them never store
            # the same game at the same time.
            task = app.configure_task("homerank.games.tasks.import_games", lock=f"user-{user.pk}")
            run.job_id = task.defer(import_run_id=run.pk)
            run.save(update_fields=["file_size", "job_id"])
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    logger.info("Import queued", import_run_id=run.pk, file_size=run.file_size)
    return run


def _save(chunks: Iterable[bytes], path: Path) -> int:
    """Write the chunks to the file and return its size; stop at the size limit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with path.open("wb") as file:
        for chunk in chunks:
            size += len(chunk)
            if size > settings.IMPORT_MAX_BYTES:
                raise ImportTooLargeError
            file.write(chunk)
    return size


def run_import(*, import_run_id: int) -> None:
    """Import the games of a queued import. Called by the job, not during a request."""
    run = ImportRun.objects.select_related("user").get(pk=import_run_id)
    path = import_path(run)
    run.status = ImportRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])
    try:
        with path.open("rb") as file:
            _import_file(run, file)
    except Exception as error:
        # The job's boundary: record why the import stopped, then let the worker log the error.
        run.status = ImportRun.Status.FAILED
        # Always kept, even when the file's broken games have used up MAX_ERRORS_KEPT.
        run.errors.append({"line": None, "reason": f"The import stopped: {error}"})
        raise
    else:
        run.status = ImportRun.Status.DONE
    finally:
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at", "errors"])
        path.unlink(missing_ok=True)
        logger.info(
            "Import finished",
            import_run_id=run.pk,
            status=run.status,
            imported=run.games_imported,
            duplicates=run.games_duplicate,
            failed=run.games_failed,
        )


@dataclass
class _NewGame:
    game: Game  # not saved yet
    parsed: chess.pgn.Game  # for its positions, computed only if the game is new


def _import_file(run: ImportRun, file: BinaryIO) -> None:
    lines = _CountedLines(file)
    batch: list[_NewGame] = []
    for item in read_pgn(lines):
        if isinstance(item, PgnError):
            run.games_failed += 1
            _add_error(run, line=item.line, reason=item.reason)
            continue
        batch.append(_new_game(run, item))
        if len(batch) == IMPORT_BATCH_SIZE:
            _save_batch(run, batch, bytes_read=lines.bytes_read)
            batch = []
    _save_batch(run, batch, bytes_read=lines.bytes_read)


def _new_game(run: ImportRun, item: PgnGame) -> _NewGame:
    headers = read_headers(item.game)
    game = Game(
        user=run.user,
        source=Game.Source.PGN,
        import_run=run,
        pgn=item.pgn,
        white=headers.white,
        black=headers.black,
        white_elo=headers.white_elo,
        black_elo=headers.black_elo,
        result=headers.result,
        date=headers.date.earliest(),
        date_pgn=str(headers.date),
        event=headers.event,
        site=headers.site,
        eco=headers.eco,
        opening=headers.opening,
        time_control=headers.time_control[:50],
        time_class=headers.time_class,
        termination=headers.termination,
        user_color=user_side(headers.white, headers.black, run.user.player_names) or "",
        ply_count=sum(1 for _ in item.game.mainline_moves()),
        dedup_hash=dedup_hash(item.game, headers),
    )
    return _NewGame(game, item.game)


def _positions(new: _NewGame) -> list[GamePosition]:
    return [
        GamePosition(
            game=new.game,
            user=new.game.user,
            ply=position.ply,
            zobrist=as_bigint(position.zobrist),
            move_san=position.move_san or "",
            move_uci=position.move_uci or "",
        )
        for position in positions(new.parsed)
    ]


def _save_batch(run: ImportRun, batch: list[_NewGame], *, bytes_read: int) -> None:
    """Store the batch's new games, skip the known ones, and update the progress with them.

    Positions take the most time to compute, so only new games get them: re-importing an export
    with a few new games is quick.
    """
    hashes = [new.game.dedup_hash for new in batch]
    known = set(
        Game.objects.filter(user=run.user, dedup_hash__in=hashes).values_list(
            "dedup_hash", flat=True
        )
    )
    new_games = []
    for new in batch:
        if new.game.dedup_hash in known:
            run.games_duplicate += 1
        else:
            known.add(new.game.dedup_hash)  # a game may also appear twice in one file
            new_games.append(new)

    with transaction.atomic():
        # On PostgreSQL bulk_create sets the games' ids, which their positions need.
        Game.objects.bulk_create([new.game for new in new_games])
        GamePosition.objects.bulk_create(
            (position for new in new_games for position in _positions(new)), batch_size=5000
        )
        run.games_imported += len(new_games)
        run.bytes_read = bytes_read
        run.save(
            update_fields=[
                "games_imported",
                "games_duplicate",
                "games_failed",
                "errors",
                "bytes_read",
            ]
        )


def _add_error(run: ImportRun, *, line: int | None, reason: str) -> None:
    if len(run.errors) < MAX_ERRORS_KEPT:
        run.errors.append({"line": line, "reason": reason})


class _CountedLines:
    """A file's lines, counting the bytes read so far for the progress bar."""

    def __init__(self, file: BinaryIO) -> None:
        self._file = file
        self.bytes_read = 0

    def __iter__(self) -> Iterator[bytes]:
        for line in self._file:
            self.bytes_read += len(line)
            yield line
