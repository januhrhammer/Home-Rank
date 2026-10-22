import datetime
from pathlib import Path

import chess
import chess.polyglot
import pytest
from procrastinate.contrib.django import app
from procrastinate.contrib.django.models import ProcrastinateJob
from procrastinate.testing import InMemoryConnector
from pytest_django import Settings

from homerank.accounts.models import User
from homerank.chesslib.positions import as_bigint
from homerank.games import services
from homerank.games.models import Game, GamePosition, ImportRun
from homerank.games.services import ImportTooLargeError, import_path, run_import, start_import

SCHOLARS_MATE = """\
[Event "Casual game"]
[Date "2024.03.05"]
[White "Uhrhammer, Jan"]
[Black "Ben"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0
"""

FOOLS_MATE = """\
[Event "Casual game"]
[Date "2024.03.06"]
[White "Ben"]
[Black "januhrhammer"]
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
"""

BROKEN = SCHOLARS_MATE.replace("Qxf7#", "Qxf8")  # an illegal move

# Two new games, a copy of the first one, and a broken game.
CLUB_FILE = "\n".join([SCHOLARS_MATE, FOOLS_MATE, SCHOLARS_MATE, BROKEN])
BROKEN_LINE = 1 + 3 * SCHOLARS_MATE.count("\n") + 3  # three games and three blank lines before it

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def data_dir(settings: Settings, tmp_path: Path) -> Path:
    settings.DATA_DIR = tmp_path
    return tmp_path


@pytest.fixture
def jan() -> User:
    return User.objects.create_user(username="jan", player_names=["Uhrhammer, Jan", "januhrhammer"])


def upload(user: User, text: str = CLUB_FILE) -> ImportRun:
    """Start an import the way an upload does: the file arrives in chunks."""
    data = text.encode()
    return start_import(user=user, file_name="club.pgn", chunks=[data[:100], data[100:]])


def imported(user: User, text: str = CLUB_FILE) -> ImportRun:
    run = upload(user, text)
    run_import(import_run_id=run.pk)
    run.refresh_from_db()
    return run


def test_start_import_saves_the_file_and_queues_the_job(jan: User) -> None:
    run = upload(jan)

    assert run.status == ImportRun.Status.QUEUED
    assert run.file_name == "club.pgn"
    assert run.file_size == len(CLUB_FILE.encode())
    assert import_path(run).read_text() == CLUB_FILE
    job = ProcrastinateJob.objects.get(id=run.job_id)
    assert job.task_name == "homerank.games.tasks.import_games"
    assert job.args == {"import_run_id": run.pk}
    assert job.lock == f"user-{jan.pk}"  # one import per user at a time


def test_start_import_refuses_files_over_the_limit(
    jan: User, settings: Settings, data_dir: Path
) -> None:
    settings.IMPORT_MAX_BYTES = 150

    with pytest.raises(ImportTooLargeError, match="at most 0 MB"):
        upload(jan)

    assert not ImportRun.objects.exists()
    assert not ProcrastinateJob.objects.exists()
    assert not list(data_dir.rglob("*.pgn"))  # no file left behind


def test_imports_the_new_games(jan: User) -> None:
    run = imported(jan)

    assert run.status == ImportRun.Status.DONE
    assert (run.games_imported, run.games_duplicate, run.games_failed) == (2, 1, 1)
    assert run.bytes_read == run.file_size
    assert run.started_at is not None
    assert run.finished_at is not None
    assert not import_path(run).exists()  # the file is deleted once imported


def test_records_why_a_game_failed(jan: User) -> None:
    run = imported(jan)

    (error,) = run.errors
    assert error["line"] == BROKEN_LINE
    assert error["reason"].startswith("illegal san: 'Qxf8'")


def test_stores_the_game_and_its_headers(jan: User) -> None:
    run = imported(jan)

    game = Game.objects.get(user=jan, white="Uhrhammer, Jan")
    assert game.pgn == SCHOLARS_MATE
    assert game.source == Game.Source.PGN
    assert game.import_run == run
    assert (game.black, game.result, game.event) == ("Ben", "1-0", "Casual game")
    assert (game.date, game.date_pgn) == (datetime.date(2024, 3, 5), "2024.03.05")
    assert (game.ply_count, game.time_class) == (7, "unknown")


def test_finds_the_users_side(jan: User) -> None:
    imported(jan)

    sides = dict(Game.objects.filter(user=jan).values_list("white", "user_color"))
    assert sides == {"Uhrhammer, Jan": "white", "Ben": "black"}


def test_stores_the_positions(jan: User) -> None:
    imported(jan)

    game = Game.objects.get(user=jan, white="Ben")
    stored = list(GamePosition.objects.filter(game=game).order_by("ply"))
    assert [p.ply for p in stored] == [0, 1, 2, 3, 4]
    assert stored[0].zobrist == as_bigint(chess.polyglot.zobrist_hash(chess.Board()))
    assert [p.move_san for p in stored] == ["f3", "e5", "g4", "Qh4#", ""]
    assert {p.user for p in stored} == {jan}


def test_importing_a_file_again_skips_its_games(jan: User) -> None:
    imported(jan)

    again = imported(jan)

    assert (again.games_imported, again.games_duplicate, again.games_failed) == (0, 3, 1)
    assert Game.objects.filter(user=jan).count() == again.games_duplicate - 1


def test_other_users_games_are_no_duplicates(jan: User) -> None:
    imported(jan)
    ben = User.objects.create_user(username="ben")

    run = imported(ben)

    assert (run.games_imported, run.games_duplicate) == (2, 1)
    assert not Game.objects.filter(user=ben).exclude(user_color="").exists()  # no names set


def test_works_in_batches(jan: User, monkeypatch: pytest.MonkeyPatch) -> None:
    """A copy in a later batch is found in the database, a copy in the same batch in memory."""
    monkeypatch.setattr(services, "IMPORT_BATCH_SIZE", 1)
    one_by_one = imported(jan)

    monkeypatch.setattr(services, "IMPORT_BATCH_SIZE", 3)
    jan_too = User.objects.create_user(username="jan2", player_names=jan.player_names)
    all_at_once = imported(jan_too)

    for run in one_by_one, all_at_once:
        assert (run.games_imported, run.games_duplicate, run.games_failed) == (2, 1, 1)
    assert GamePosition.objects.filter(user=jan).count() == (7 + 1) + (4 + 1)


def test_keeps_only_the_first_errors(jan: User, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "MAX_ERRORS_KEPT", 2)

    copies = 3
    run = imported(jan, "\n".join([BROKEN] * copies))

    assert run.games_failed == copies
    second_game = 1 + BROKEN.count("\n") + 1  # after the first game and a blank line
    assert [error["line"] for error in run.errors] == [1, second_game]


def test_a_failing_import_is_recorded(jan: User, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "MAX_ERRORS_KEPT", 0)  # why it stopped is kept regardless
    run = upload(jan)
    import_path(run).unlink()  # e.g. the data volume was replaced in between

    with pytest.raises(FileNotFoundError):
        run_import(import_run_id=run.pk)

    run.refresh_from_db()
    assert run.status == ImportRun.Status.FAILED
    assert run.errors[-1]["reason"].startswith("The import stopped:")
    assert run.finished_at is not None


# transaction=True: the worker runs the job in another thread with its own database connection,
# which only sees committed data.
@pytest.mark.django_db(transaction=True)
def test_the_worker_runs_the_import(jan: User) -> None:
    with app.replace_connector(InMemoryConnector()) as in_memory_app:
        run = upload(jan)
        in_memory_app.run_worker(wait=False, install_signal_handlers=False, listen_notify=False)

    run.refresh_from_db()
    assert run.status == ImportRun.Status.DONE
    assert (run.games_imported, run.games_duplicate, run.games_failed) == (2, 1, 1)


def test_positions_are_only_computed_for_new_games(
    jan: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-uploading a whole export to add a few games mostly finds known ones: keep that quick."""
    imported(jan)
    computed: list[object] = []

    def counted_positions(game: object) -> list[object]:
        computed.append(game)
        return []

    monkeypatch.setattr(services, "positions", counted_positions)

    imported(jan)

    assert computed == []
