"""Importing PGN files into reference databases: reading, batches, resuming, indexing."""

from pathlib import Path

import chess
import chess.polyglot
import pytest
import zstandard
from django.core.management import CommandError, call_command
from procrastinate.contrib.django.models import ProcrastinateJob
from pytest_django import Settings

from homerank.chesslib.positions import as_bigint
from homerank.reference import repository, services, tasks
from homerank.reference.models import ReferenceDatabase, ReferenceGame, ReferenceImport
from homerank.reference.repository import games_at
from homerank.reference.services import (
    ImportPathError,
    ImportStateError,
    create_database,
    estimate,
    import_file_path,
    resume_import,
    run_import,
    start_import,
)

pytestmark = pytest.mark.django_db

START = as_bigint(chess.polyglot.zobrist_hash(chess.Board()))


def game(white: str, moves: str, result: str = "*") -> bytes:
    return f'[White "{white}"]\n[Black "X"]\n[Result "{result}"]\n\n{moves} {result}\n\n'.encode()


GAMES = [
    game("A", "1. e4 e5 2. Nf3 Nc6", "1-0"),
    game("B", "1. d4 d5 2. c4", "0-1"),
    game("C", "1. e4 c5 2. Qh9"),  # broken: Qh9
    game("A", "1. e4 e5 2. Nf3 Nc6", "1-0"),  # the first one again
    game("D", "1. c4 e5", "1/2-1/2"),
]


@pytest.fixture
def import_dir(settings: Settings, tmp_path: Path) -> Path:
    settings.REFERENCE_IMPORT_DIR = tmp_path
    return tmp_path


def write_zst(path: Path, games: list[bytes]) -> Path:
    path.write_bytes(zstandard.ZstdCompressor().compress(b"".join(games)))
    return path


def imported(database: ReferenceDatabase, *names: str) -> ReferenceImport:
    reference_import = start_import(database=database, files=list(names))
    run_import(import_id=reference_import.pk, workers=2)
    reference_import.refresh_from_db()
    database.refresh_from_db()
    return reference_import


def test_imports_a_compressed_file_skipping_duplicates_and_broken_games(import_dir: Path) -> None:
    write_zst(import_dir / "masters.pgn.zst", GAMES)
    database = create_database(name="Masters")

    reference_import = imported(database, "masters.pgn.zst")

    assert reference_import.status == ReferenceImport.Status.DONE
    assert database.status == ReferenceDatabase.Status.READY
    assert database.game_count == 3  # noqa: PLR2004 - five games, one broken, one twice
    whites = sorted(ReferenceGame.objects.values_list("white", flat=True))
    assert whites == ["A", "B", "D"]
    file = reference_import.files.get()
    assert (file.games_read, file.games_failed, file.done, file.progress) == (4, 1, True, 1.0)
    assert file.errors[0]["offset"] == len(GAMES[0]) + len(GAMES[1])
    assert "Qh9" in file.errors[0]["reason"]
    assert len(games_at(database.pk, START)) == len(whites)  # every game, once


class PowerCutError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("the power went out")


def test_an_interrupted_import_resumes_after_the_last_stored_batch(
    import_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_zst(import_dir / "masters.pgn.zst", GAMES)
    database = create_database(name="Masters")
    monkeypatch.setattr(services, "CHUNK_GAMES", 1)
    monkeypatch.setattr(services, "BATCH_GAMES", 2)
    real_copy = repository.copy_games
    calls = 0

    def crash_on_the_second_batch(rows: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:  # noqa: PLR2004
            raise PowerCutError
        real_copy(rows)  # type: ignore[arg-type]

    monkeypatch.setattr(repository, "copy_games", crash_on_the_second_batch)
    reference_import = start_import(database=database, files=["masters.pgn.zst"])
    with pytest.raises(PowerCutError):
        run_import(import_id=reference_import.pk, workers=1)
    reference_import.refresh_from_db()
    file = reference_import.files.get()
    assert reference_import.status == ReferenceImport.Status.FAILED
    # The first batch stored the first game and left the second (read ahead) for the next.
    assert file.offset == len(GAMES[0])
    assert ReferenceGame.objects.count() == 1

    monkeypatch.setattr(repository, "copy_games", real_copy)
    run_import(import_id=reference_import.pk, workers=1)

    database.refresh_from_db()
    assert database.game_count == 3  # noqa: PLR2004 - no game twice, none lost
    file.refresh_from_db()
    # Each game was read once: the first before the crash, the others after resuming.
    assert (file.games_read, file.games_failed) == (4, 1)
    assert len(games_at(database.pk, START)) == 3  # noqa: PLR2004 - the first batch indexed too


def test_a_second_import_keeps_the_first_ones_games_searchable(import_dir: Path) -> None:
    write_zst(import_dir / "one.pgn.zst", GAMES[:2])
    write_zst(import_dir / "two.pgn.zst", [GAMES[4], GAMES[0]])  # a new game and a known one
    database = create_database(name="Masters")
    imported(database, "one.pgn.zst")

    imported(database, "two.pgn.zst")

    assert database.game_count == 3  # noqa: PLR2004
    assert {e.game_id for e in games_at(database.pk, START)} == set(
        ReferenceGame.objects.values_list("id", flat=True)
    )


def test_a_failed_import_can_be_queued_again(import_dir: Path) -> None:
    write_zst(import_dir / "masters.pgn.zst", GAMES)
    database = create_database(name="Masters")
    reference_import = start_import(database=database, files=["masters.pgn.zst"])
    ProcrastinateJob.objects.filter(id=reference_import.job_id).update(status="failed")
    ReferenceImport.objects.filter(pk=reference_import.pk).update(
        status=ReferenceImport.Status.FAILED, error="No space left on device"
    )

    resumed = resume_import(ReferenceImport.objects.get(pk=reference_import.pk))

    assert resumed.pk == reference_import.pk  # the same import, carrying on where it stopped
    assert (resumed.status, resumed.error) == (ReferenceImport.Status.QUEUED, "")
    job = ProcrastinateJob.objects.get(id=resumed.job_id)
    assert (job.status, job.lock) == ("todo", f"reference-{database.pk}")
    run_import(import_id=resumed.pk, workers=1)
    database.refresh_from_db()
    assert database.game_count == 3  # noqa: PLR2004


def test_a_finished_or_waiting_import_is_not_queued_again(import_dir: Path) -> None:
    write_zst(import_dir / "masters.pgn.zst", GAMES[:1])
    database = create_database(name="Masters")
    waiting = start_import(database=database, files=["masters.pgn.zst"])

    with pytest.raises(ImportStateError, match="already queued or running"):
        resume_import(waiting)
    ProcrastinateJob.objects.filter(id=waiting.job_id).update(status="succeeded")
    run_import(import_id=waiting.pk, workers=1)
    waiting.refresh_from_db()
    with pytest.raises(ImportStateError, match="finished"):
        resume_import(waiting)


def test_the_command_needs_a_database_name(import_dir: Path) -> None:
    write_zst(import_dir / "masters.pgn.zst", GAMES[:1])

    with pytest.raises(CommandError, match="--name"):
        call_command("import_reference", "masters.pgn.zst", "--name", " ")

    assert not ReferenceDatabase.objects.exists()


def test_an_import_is_queued_on_the_bulk_queue(import_dir: Path) -> None:
    write_zst(import_dir / "masters.pgn.zst", GAMES)
    database = create_database(name="Masters")

    reference_import = start_import(database=database, files=["masters.pgn.zst"])

    job = ProcrastinateJob.objects.get(id=reference_import.job_id)
    assert (job.task_name, job.queue_name) == ("homerank.reference.tasks.import_reference", "bulk")
    assert job.lock == f"reference-{database.pk}"


def test_the_job_runs_the_import(import_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_zst(import_dir / "masters.pgn.zst", GAMES[:1])
    database = create_database(name="Masters")
    reference_import = start_import(database=database, files=["masters.pgn.zst"])
    monkeypatch.setattr("django.conf.settings.REFERENCE_IMPORT_WORKERS", 1)

    tasks.import_reference(import_id=reference_import.pk)

    reference_import.refresh_from_db()
    assert reference_import.status == ReferenceImport.Status.DONE


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("../secret.pgn", "not in the import folder"),
        ("missing.pgn", "no such file"),
        ("notes.txt", "not a PGN file"),
    ],
)
def test_only_pgn_files_in_the_import_folder_can_be_imported(
    import_dir: Path, name: str, reason: str
) -> None:
    (import_dir / "notes.txt").write_text("hello")
    (import_dir.parent / "secret.pgn").write_text('[White "x"]\n\n*\n')

    with pytest.raises(ImportPathError, match=reason):
        import_file_path(name)


def test_lists_the_importable_files(import_dir: Path) -> None:
    (import_dir / "periods").mkdir()
    for name in ("periods/1990.pgn.zst", "periods/2000.7z", "readme.txt", "a.pgn"):
        (import_dir / name).write_bytes(b"x")

    assert [str(p) for p in services.importable_files()] == [
        "a.pgn",
        "periods/1990.pgn.zst",
        "periods/2000.7z",
    ]


def test_estimates_games_and_disk_space(import_dir: Path) -> None:
    path = import_dir / "big.pgn.zst"
    path.write_bytes(b"x" * 190_000)

    result = estimate([path], depth=30)

    assert result.games == 1000  # noqa: PLR2004
    assert result.disk_bytes == 1000 * (410 + 30 * 21)
    assert result.peak_bytes == 2 * result.disk_bytes  # while the indexes are built


def test_deleting_a_database_drops_its_games(import_dir: Path) -> None:
    write_zst(import_dir / "masters.pgn.zst", GAMES[:2])
    database = create_database(name="Masters")
    imported(database, "masters.pgn.zst")

    services.delete_database(database)

    assert not ReferenceDatabase.objects.exists()
    assert ReferenceGame.objects.count() == 0
