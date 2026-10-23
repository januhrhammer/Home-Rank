"""Automatic analysis of new games, and the hours it may run in."""

import itertools
from datetime import UTC, date, datetime, time

import pytest
from django.utils import timezone
from pytest_django import Settings

from homerank.accounts.models import User
from homerank.analysis import services, tasks
from homerank.analysis.models import AnalysisRun, AnalysisSettings
from homerank.analysis.services import queue_auto_analyses, within_analysis_hours
from homerank.games.models import Game

pytestmark = pytest.mark.django_db

_hashes = itertools.count()


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


def make_game(user: User, *, user_color: str = "white", day: int = 1) -> Game:
    return Game.objects.create(
        user=user,
        source=Game.Source.PGN,
        pgn="1. e4 e5 *\n",
        result="*",
        date=date(2026, 10, day),
        date_pgn=f"2026.10.{day:02}",
        time_class="unknown",
        ply_count=2,
        user_color=user_color,
        dedup_hash=f"{next(_hashes):064}",
    )


def queued_games(user: User) -> set[Game]:
    return {run.game for run in AnalysisRun.objects.filter(user=user, status="queued")}


def test_queues_the_games_the_user_played(alice: User) -> None:
    mine = make_game(alice, user_color="black")
    others = make_game(alice, user_color="")  # e.g. from a tournament file

    assert queue_auto_analyses() == 1

    assert queued_games(alice) == {mine}
    assert others not in queued_games(alice)


def test_only_a_few_wait_at_a_time_the_newest_first(
    alice: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(services, "AUTO_QUEUE_PER_USER", 2)
    games = [make_game(alice, day=day) for day in (1, 2, 3)]

    queue_auto_analyses()
    assert queued_games(alice) == {games[2], games[1]}

    assert queue_auto_analyses() == 0  # still two waiting
    AnalysisRun.objects.filter(game=games[2]).update(status="done")
    queue_auto_analyses()
    assert queued_games(alice) == {games[1], games[0]}


def test_a_game_whose_analysis_failed_isnt_tried_again(alice: User) -> None:
    game = make_game(alice)
    AnalysisRun.objects.create(user=alice, game=game, depth=18, status="failed")

    assert queue_auto_analyses() == 0


def test_users_can_turn_it_off(alice: User) -> None:
    make_game(alice)
    AnalysisSettings.objects.create(user=alice, auto_analyse=False)

    assert queue_auto_analyses() == 0


def test_nothing_is_queued_outside_the_analysis_hours(
    alice: User, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_game(alice)
    settings.ANALYSIS_HOURS = (time(23, 0), time(7, 0))
    noon = datetime(2026, 10, 23, 12, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: noon)

    assert queue_auto_analyses() == 0


@pytest.mark.parametrize(
    ("hours", "local", "expected"),
    [
        (None, time(12, 0), True),
        ((time(23, 0), time(7, 0)), time(23, 0), True),
        ((time(23, 0), time(7, 0)), time(3, 0), True),
        ((time(23, 0), time(7, 0)), time(7, 0), False),
        ((time(23, 0), time(7, 0)), time(12, 0), False),
        ((time(9, 0), time(17, 0)), time(12, 0), True),
        ((time(9, 0), time(17, 0)), time(18, 0), False),
    ],
)
def test_analysis_hours_may_pass_midnight(
    settings: Settings, hours: tuple[time, time] | None, local: time, expected: bool
) -> None:
    settings.ANALYSIS_HOURS = hours
    now = datetime.combine(date(2026, 10, 23), local, tzinfo=UTC)

    assert within_analysis_hours(now) is expected


def test_analysis_hours_are_in_the_servers_time_zone(settings: Settings) -> None:
    settings.TIME_ZONE = "Europe/Berlin"
    settings.ANALYSIS_HOURS = (time(23, 0), time(7, 0))

    # 22:30 UTC is 00:30 in Berlin in summer time.
    assert within_analysis_hours(datetime(2026, 7, 1, 22, 30, tzinfo=UTC)) is True


def test_the_periodic_job_queues_them(alice: User) -> None:
    game = make_game(alice)

    tasks.queue_auto_analyses(timestamp=0)

    assert queued_games(alice) == {game}
