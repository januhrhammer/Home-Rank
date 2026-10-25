"""Novelty searches: the opponent's rating, starting and stopping, and the job (ADR 0022)."""

import time

import chess
import pytest
from django.http import Http404
from procrastinate.contrib.django.models import ProcrastinateJob

from homerank.accounts.models import User
from homerank.engine.tests.scripted import ENGINE, MODEL, ScriptedEngine, ScriptedModel
from homerank.novelty import selectors, services
from homerank.novelty.models import NoveltySearch, SearchStatus
from homerank.novelty.services import (
    InvalidStartError,
    SearchFinishedError,
    cancel_search,
    lichess_rating,
    run_search,
    start_search,
)
from homerank.reference.tests.conftest import load_reference

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


def started(user: User, **fields: object) -> NoveltySearch:
    values: dict[str, object] = {
        "fen": chess.STARTING_FEN,
        "moves": [],
        "label": "",
        "side": "white",
        "rating": 1800,
        "rating_kind": "fide",
        "budget_cp": 150,
        "limit_minutes": 60,
        **fields,
    }
    return start_search(user=user, **values)  # type: ignore[arg-type]


def scripted_run(search: NoveltySearch, **kwargs: object) -> NoveltySearch:
    run_search(
        search.pk,
        engines=[ScriptedEngine(ENGINE), ScriptedEngine(ENGINE)],
        model=ScriptedModel(MODEL),
        **kwargs,  # type: ignore[arg-type]
    )
    search.refresh_from_db()
    return search


@pytest.mark.parametrize(
    ("rating", "kind", "expected"),
    [
        (1800, "lichess", 1800),
        (1400, "fide", 1600),  # + 200 up to 1500
        (1500, "fide", 1700),
        (1900, "fide", 2050),  # halfway to 2300: + 150
        (2300, "fide", 2400),  # + 100 from 2300 on
        (2500, "fide", 2600),
        (1500, "dwz", 1750),
        (1900, "dwz", 2075),
    ],
)
def test_the_opponents_rating_becomes_a_lichess_rating(
    rating: int, kind: str, expected: int
) -> None:
    assert lichess_rating(rating, kind) == expected


def test_a_search_is_queued_one_at_a_time_with_its_lichess_rating(alice: User) -> None:
    search = started(alice, rating=1500, rating_kind="dwz", limit_minutes=10_000)
    chosen = started(alice, elo=1650)

    job = ProcrastinateJob.objects.get(id=search.job_id)
    assert (job.task_name, job.queue_name, job.lock) == (
        "homerank.novelty.tasks.novelty_search",
        "novelty",
        "novelty",
    )
    assert (search.elo, search.status) == (1750, SearchStatus.QUEUED)
    assert search.limit_minutes == 12 * 60  # at most
    assert chosen.elo == 1650  # the user's own choice wins  # noqa: PLR2004


@pytest.mark.parametrize(
    "fen", ["not a position", "8/8/8/8/8/8/8/8 w - - 0 1", "7k/5QQ1/8/8/8/8/8/K7 b - - 0 1"]
)
def test_a_search_needs_a_valid_position_with_moves_left(alice: User, fen: str) -> None:
    with pytest.raises(InvalidStartError):
        started(alice, fen=fen)


def test_the_job_stores_the_tries_of_each_step(alice: User) -> None:
    search = scripted_run(started(alice))

    assert (search.status, search.own_moves) == (SearchStatus.DONE, 4)
    first = selectors.tries(search).first()
    assert first is not None
    assert (first.rank, first.san, first.best_san) == (0, "g4", "e4")
    assert first.refutation[0]["san"] == "d5"
    assert first.reference_games is None  # no reference database here
    assert search.started_at is not None
    assert search.finished_at is not None


def test_each_try_says_how_often_a_reference_database_has_its_position(alice: User) -> None:
    load_reference()  # two games: neither starts 1.g4

    search = scripted_run(started(alice))

    assert [t.reference_games for t in selectors.tries(search)] == [0]


def test_the_time_limit_ends_a_search_keeping_what_it_found(
    alice: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The hour is up once the first step is stored.
    now = 0.0
    real_store = services._store

    def store_then_an_hour_passes(*args: object) -> None:
        nonlocal now
        real_store(*args)  # type: ignore[arg-type]
        now = 3600.0

    monkeypatch.setattr(services, "_store", store_then_an_hour_passes)
    search = scripted_run(started(alice, limit_minutes=60), clock=lambda: now)

    assert search.status == SearchStatus.DONE
    assert search.own_moves == 2  # noqa: PLR2004
    assert search.tries.exists()


def test_a_search_cancelled_before_it_runs_doesnt_start(alice: User) -> None:
    waiting = cancel_search(started(alice))

    assert waiting.status == SearchStatus.CANCELLED
    assert scripted_run(waiting).own_moves == 0  # the job finds it cancelled and does nothing


# Committed for real: the search's watcher reads the database on a connection of its own.
@pytest.mark.django_db(transaction=True)
def test_a_running_search_stops_when_cancelled_keeping_what_it_found(
    alice: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    running = started(alice)
    real_store = services._store

    def cancel_after_the_first_step(*args: object) -> None:
        real_store(*args)  # type: ignore[arg-type]
        NoveltySearch.objects.filter(pk=running.pk).update(cancel_requested=True)
        time.sleep(0.05)  # for the watcher to see it

    monkeypatch.setattr(services, "_store", cancel_after_the_first_step)
    monkeypatch.setattr(services, "CANCEL_CHECK_SECONDS", 0.01)
    stopped = scripted_run(running)

    assert (stopped.status, stopped.own_moves) == (SearchStatus.CANCELLED, 2)
    assert stopped.tries.exists()
    with pytest.raises(SearchFinishedError):
        cancel_search(stopped)


def test_a_failing_search_says_why(alice: User) -> None:
    search = started(alice)

    class EngineCrashedError(RuntimeError):
        def __init__(self) -> None:
            super().__init__("engine crashed")

    class Broken:
        def lines(self, board: chess.Board, *, depth: int, count: int) -> list[object]:
            raise EngineCrashedError

    with pytest.raises(EngineCrashedError):
        run_search(search.pk, engines=[Broken()], model=ScriptedModel(MODEL))  # type: ignore[list-item]

    search.refresh_from_db()
    assert (search.status, search.error) == (SearchStatus.FAILED, "engine crashed")


def test_users_see_only_their_own_searches(alice: User) -> None:
    search = started(alice)
    bob = User.objects.create_user(username="bob")

    assert list(selectors.searches(user=alice)) == [search]
    assert list(selectors.searches(user=bob)) == []
    with pytest.raises(Http404):
        selectors.search(user=bob, search_id=search.pk)
