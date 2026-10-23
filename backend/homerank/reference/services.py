"""Creating reference databases and importing PGN files into them (ADR 0015).

start_import queues an import of files from REFERENCE_IMPORT_DIR; run_import, which the job and
`manage.py import_reference` call, reads them with a pool of worker processes, writes games and
their positions with COPY in batches, notes after each batch where each file stands, and finally
removes duplicates and builds the explorer and position index.
"""

import io
import multiprocessing
import multiprocessing.pool
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from procrastinate.contrib.django import app

from homerank.accounts.models import User
from homerank.chesslib import bulk
from homerank.chesslib.archives import SUFFIXES, open_pgn, split_games
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.core.errors import DomainError
from homerank.games.models import Collection, Game
from homerank.games.services import add_games, new_game, store_games
from homerank.reference import repository
from homerank.reference.models import (
    ReferenceDatabase,
    ReferenceGame,
    ReferenceImport,
    ReferenceImportFile,
)
from homerank.reference.selectors import pgn_of

logger = structlog.get_logger(__name__)

# Games a worker process parses per task, and games stored per transaction (with the files'
# offsets, so that an interrupted import resumes after the last stored batch).
CHUNK_GAMES = 500
BATCH_GAMES = 10_000
MAX_ERRORS_KEPT = 100


class ImportPathError(DomainError):
    status = HTTPStatus.UNPROCESSABLE_ENTITY

    def __init__(self, path: str, reason: str) -> None:
        self.detail = f"{path}: {reason}"
        super().__init__(self.detail)


def create_database(
    *, name: str, description: str = "", depth: int = bulk.DEFAULT_DEPTH
) -> ReferenceDatabase:
    with transaction.atomic():
        database = ReferenceDatabase.objects.create(name=name, description=description, depth=depth)
        repository.create_partitions(database.pk)
    logger.info("Reference database created", database_id=database.pk, name=name)
    return database


def delete_database(database: ReferenceDatabase) -> None:
    """Delete the database and its games at once: its partitions are dropped."""
    with transaction.atomic():
        repository.drop_partitions(database.pk)
        database.delete()


def import_file_path(relative: str) -> Path:
    """A file in REFERENCE_IMPORT_DIR, by its path relative to it; refuses anything else."""
    folder = Path(settings.REFERENCE_IMPORT_DIR).resolve()
    path = (folder / relative).resolve()
    if not path.is_relative_to(folder):
        raise ImportPathError(relative, "not in the import folder")
    if not path.is_file():
        raise ImportPathError(relative, "no such file")
    if not path.name.lower().endswith(SUFFIXES):
        raise ImportPathError(relative, f"not a PGN file ({', '.join(SUFFIXES)})")
    return path


def importable_files() -> list[Path]:
    """The PGN files in REFERENCE_IMPORT_DIR (and its subfolders), relative to it."""
    folder = Path(settings.REFERENCE_IMPORT_DIR)
    if not folder.is_dir():
        return []
    return sorted(
        p.relative_to(folder)
        for p in folder.rglob("*")
        if p.is_file() and p.name.lower().endswith(SUFFIXES)
    )


@dataclass(frozen=True)
class Estimate:
    games: int
    disk_bytes: int


# Compressed bytes per game, measured on Lichess's database (zst) and typical PGN files; and the
# space a game takes once imported (with its search indexes), plus its explorer and position
# index per indexed ply. Measured with 1.5 million Lichess games: 611 MB of games, 939 MB of
# explorer and index at 30 plies.
BYTES_PER_GAME = {".pgn": 900, ".gz": 250, ".bz2": 200, ".zst": 190, ".7z": 180}
STORED_BYTES_PER_GAME = 410
INDEX_BYTES_PER_PLY = 21


def estimate(paths: list[Path], depth: int) -> Estimate:
    """Roughly how many games the files hold, and the disk space they will take once imported."""
    games = sum(p.stat().st_size // BYTES_PER_GAME[p.suffix.lower()] for p in paths)
    return Estimate(games, games * (STORED_BYTES_PER_GAME + depth * INDEX_BYTES_PER_PLY))


def start_import(*, database: ReferenceDatabase, files: list[str]) -> ReferenceImport:
    """Queue an import of the files (paths relative to REFERENCE_IMPORT_DIR) on the "bulk"
    queue. One import per database runs at a time."""
    paths = [import_file_path(name) for name in files]
    with transaction.atomic():
        reference_import = create_import(database, paths)
        task = app.configure_task(
            "homerank.reference.tasks.import_reference",
            lock=f"reference-{database.pk}",
            queue="bulk",
        )
        reference_import.job_id = task.defer(import_id=reference_import.pk)
        reference_import.save(update_fields=["job_id"])
    return reference_import


def create_import(database: ReferenceDatabase, paths: list[Path]) -> ReferenceImport:
    reference_import = ReferenceImport.objects.create(database=database)
    ReferenceImportFile.objects.bulk_create(
        ReferenceImportFile(reference_import=reference_import, path=str(p), size=p.stat().st_size)
        for p in paths
    )
    return reference_import


def run_import(*, import_id: int, workers: int | None = None) -> None:
    """Import the files, or carry on with an interrupted import. Called by the job or the
    management command, not during a request."""
    reference_import = ReferenceImport.objects.select_related("database").get(pk=import_id)
    database = reference_import.database
    _set_status(reference_import, ReferenceImport.Status.READING, started=True)
    database.status = ReferenceDatabase.Status.IMPORTING
    database.save(update_fields=["status"])
    workers = workers or settings.REFERENCE_IMPORT_WORKERS
    context = multiprocessing.get_context("spawn")  # the worker runs threads: don't fork it
    try:
        with context.Pool(workers) as pool:
            _prepare_staging(database, pool)
            for file in reference_import.files.filter(done=False).order_by("pk"):
                _read_file(database, file, pool)
            _set_status(reference_import, ReferenceImport.Status.INDEXING)
            removed = repository.remove_duplicates(database.pk)
            repository.build_index(database.pk)
    except Exception as error:
        reference_import.error = str(error) or type(error).__name__
        _set_status(reference_import, ReferenceImport.Status.FAILED, finished=True)
        database.status = ReferenceDatabase.Status.FAILED
        database.save(update_fields=["status"])
        raise
    database.status = ReferenceDatabase.Status.READY
    database.game_count = ReferenceGame.objects.filter(database=database).count()
    database.imported_at = timezone.now()
    database.save(update_fields=["status", "game_count", "imported_at"])
    _set_status(reference_import, ReferenceImport.Status.DONE, finished=True)
    logger.info(
        "Reference import finished",
        import_id=import_id,
        games=database.game_count,
        duplicates=removed,
    )


def _in_order[T, R](
    pool: multiprocessing.pool.Pool, function: Callable[[T], R], items: Iterable[T]
) -> Iterator[R]:
    """function(item) for each item, computed by the pool, returned in order.

    The items are read here, in the calling thread, a few ahead of the results: unlike
    pool.imap, which reads them in a thread of its own where Django would open a second
    database connection.
    """
    pending: deque[multiprocessing.pool.AsyncResult[R]] = deque()
    window = 2 * pool._processes  # type: ignore[attr-defined]
    for item in items:
        pending.append(pool.apply_async(function, (item,)))
        if len(pending) >= window:
            yield pending.popleft().get()
    while pending:
        yield pending.popleft().get()


def _set_status(
    reference_import: ReferenceImport,
    status: str,
    *,
    started: bool = False,
    finished: bool = False,
) -> None:
    reference_import.status = status
    if started:
        reference_import.started_at = timezone.now()
    if finished:
        reference_import.finished_at = timezone.now()
    reference_import.save(update_fields=["status", "error", "started_at", "finished_at"])


def _prepare_staging(database: ReferenceDatabase, pool: multiprocessing.pool.Pool) -> None:
    """Start the staging table with the positions of the games stored before, if any.

    Positions of earlier imports were dropped after indexing them, and an interrupted import's
    staging table may have been emptied by a crash (it is unlogged): index everything there is
    again, from the stored games' packed moves.
    """
    repository.drop_staging(database.pk)
    repository.create_staging(database.pk)
    rows = (
        ReferenceGame.objects.filter(database=database)
        .order_by("id")
        .values_list("id", "start_fen", "moves")
    )

    def chunks() -> Iterator[tuple[list[tuple[int, str, bytes]], int]]:
        chunk: list[tuple[int, str, bytes]] = []
        for game_id, start_fen, moves in rows.iterator(chunk_size=CHUNK_GAMES * 4):
            chunk.append((game_id, start_fen, bytes(moves)))
            if len(chunk) == CHUNK_GAMES:
                yield chunk, database.depth
                chunk = []
        if chunk:
            yield chunk, database.depth

    for positions in _in_order(pool, bulk.reindex_job, chunks()):
        repository.copy_positions(database.pk, positions)


def _read_file(
    database: ReferenceDatabase, file: ReferenceImportFile, pool: multiprocessing.pool.Pool
) -> None:
    """Read one file from where it stopped, storing its games in batches."""
    with open_pgn(Path(file.path)) as stream:
        if file.offset:
            stream.skip_to(file.offset)
        base = stream.offset  # split_games counts from here

        def chunks() -> Iterator[tuple[list[tuple[int, bytes]], int]]:
            chunk: list[tuple[int, bytes]] = []
            for offset, text in split_games(iter(stream)):
                chunk.append((base + offset, text))
                if len(chunk) == CHUNK_GAMES:
                    yield chunk, database.depth
                    chunk = []
            if chunk:
                yield chunk, database.depth

        batch: list[tuple[int, bulk.BulkGame | bulk.BulkError]] = []
        for results in _in_order(pool, bulk.parse_job, chunks()):
            batch.extend(results)
            if len(batch) >= BATCH_GAMES:
                # Reading is ahead of the batch by a few chunks: resume where its last game
                # starts, and leave that game for the next batch.
                *stored, (resume_at, last) = batch
                _store(database, file, stored, offset=resume_at, progress=stream.progress)
                batch = [(resume_at, last)]
        _store(database, file, batch, offset=stream.offset, progress=1.0)
    file.done = True
    file.save(update_fields=["done"])


def _store(
    database: ReferenceDatabase,
    file: ReferenceImportFile,
    batch: list[tuple[int, bulk.BulkGame | bulk.BulkError]],
    *,
    offset: int,
    progress: float,
) -> None:
    """Write a batch of games and their positions, and note how far the file is read, in one
    transaction: after a crash, reading resumes right after the last stored batch."""
    games = [game for _, game in batch if isinstance(game, bulk.BulkGame)]
    with transaction.atomic():
        first = repository.next_game_id(database.pk)
        repository.copy_games(
            repository.game_row(database.pk, first + i, game) for i, game in enumerate(games)
        )
        repository.copy_positions(
            database.pk,
            (
                row
                for i, game in enumerate(games)
                for row in repository.position_rows(first + i, game)
            ),
        )
        for start, result in batch:
            if isinstance(result, bulk.BulkError):
                file.games_failed += 1
                if len(file.errors) < MAX_ERRORS_KEPT:
                    file.errors.append({"offset": start, "reason": result.reason})
        file.games_read += len(games)
        file.offset = offset
        file.progress = progress
        file.save(update_fields=["games_read", "games_failed", "errors", "progress", "offset"])
    logger.info(
        "Reference games stored",
        database_id=database.pk,
        file=Path(file.path).name,
        games=file.games_read,
        failed=file.games_failed,
        progress=round(progress, 4),
    )


class UnreadableGameError(DomainError):
    status = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, reason: str) -> None:
        self.detail = f"The stored game can't be read: {reason}"
        super().__init__(self.detail)


def copy_game(
    *, user: User, game: ReferenceGame, collection: Collection | None
) -> tuple[Game, bool]:
    """Copy a reference game into the user's games (or find the copy they have), and add it to
    the collection if given. Returns the user's game and whether it is new."""
    items = list(read_pgn(io.BytesIO(pgn_of(game).encode())))
    item = items[0]
    if not isinstance(item, PgnGame):  # can't happen: the moves were legal when imported
        raise UnreadableGameError(item.reason)
    new = new_game(user, item)
    stored = store_games(user, [new])
    copy = Game.objects.get(user=user, dedup_hash=new.game.dedup_hash)
    if collection is not None:
        add_games(collection, game_ids=[copy.pk])
    return copy, stored.imported == 1
