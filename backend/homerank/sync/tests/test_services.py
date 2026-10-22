"""Linking accounts and syncing them, with the sites' answers recorded (see test_clients)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob
from pytest_django import Settings

from homerank.accounts.models import User
from homerank.games.models import Game
from homerank.sync import services, tasks
from homerank.sync.models import LinkedAccount, SyncRun
from homerank.sync.services import AccountTakenError, link_account, run_sync, start_sync

FIXTURES = Path(__file__).parent / "fixtures"
LICHESS = LinkedAccount.Platform.LICHESS
CHESSCOM = LinkedAccount.Platform.CHESSCOM

pytestmark = pytest.mark.django_db

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice", player_names=["Alice Example"])


class FakeSites:
    """Answers the sync's requests instead of Lichess and Chess.com, and records them."""

    def __init__(self) -> None:
        self.handler: Handler = lambda request: httpx.Response(404)
        self.requests: list[httpx.Request] = []

    def client(self, *, user_agent: str) -> httpx.Client:
        def handle(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return self.handler(request)

        return httpx.Client(
            headers={"User-Agent": user_agent}, transport=httpx.MockTransport(handle)
        )

    @property
    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


@pytest.fixture
def sites(monkeypatch: pytest.MonkeyPatch) -> FakeSites:
    fake = FakeSites()
    monkeypatch.setattr(services, "new_client", fake.client)
    return fake


def account(user: User, platform: str = LICHESS, username: str = "alice64") -> LinkedAccount:
    return LinkedAccount.objects.create(user=user, platform=platform, username=username)


def synced(linked: LinkedAccount) -> SyncRun:
    run = start_sync(linked)
    run_sync(sync_run_id=run.pk)
    run.refresh_from_db()
    linked.refresh_from_db()
    return run


def jobs(task: str) -> list[ProcrastinateJob]:
    return list(ProcrastinateJob.objects.filter(task_name=task))


# ---------------------------------------------------------------- linking


def test_linking_an_account_adds_the_username_and_syncs_it(alice: User) -> None:
    linked = link_account(user=alice, platform=LICHESS, username="alice64")

    alice.refresh_from_db()
    assert alice.player_names == ["Alice Example", "alice64"]
    (recompute,) = jobs("homerank.games.tasks.recompute_user_colors")
    (sync,) = jobs("homerank.sync.tasks.sync_account")
    run = SyncRun.objects.get(account=linked)
    assert sync.args == {"sync_run_id": run.pk}
    assert sync.queue_name == "sync"
    assert sync.lock == recompute.lock == f"user-{alice.pk}"  # like the user's imports
    assert recompute.id < sync.id  # sides are recomputed first


def test_a_username_already_among_the_player_names_isnt_added_again(alice: User) -> None:
    link_account(user=alice, platform=LICHESS, username="alice example")

    alice.refresh_from_db()
    assert alice.player_names == ["Alice Example"]
    assert jobs("homerank.games.tasks.recompute_user_colors") == []


def test_an_account_can_be_linked_once(alice: User) -> None:
    link_account(user=alice, platform=LICHESS, username="alice64")

    with pytest.raises(AccountTakenError, match='already linked the Lichess account "Alice64"'):
        link_account(user=alice, platform=LICHESS, username="Alice64")
    assert LinkedAccount.objects.count() == 1
    assert len(jobs("homerank.sync.tasks.sync_account")) == 1


def test_unlinking_keeps_the_games(alice: User, sites: FakeSites) -> None:
    linked = account(alice)
    sites.handler = lambda request: httpx.Response(
        200, content=(FIXTURES / "lichess_games.ndjson").read_bytes()
    )
    synced(linked)

    games = set(Game.objects.filter(user=alice))

    services.unlink_account(linked)

    assert set(Game.objects.filter(user=alice)) == games
    assert games


# ---------------------------------------------------------------- sync now


def test_syncing_again_while_a_sync_is_queued_returns_that_sync(alice: User) -> None:
    linked = account(alice)
    first = start_sync(linked)

    assert start_sync(linked) == first
    assert SyncRun.objects.count() == 1


def test_a_sync_whose_job_is_gone_doesnt_block_the_next(alice: User) -> None:
    linked = account(alice)
    stuck = start_sync(linked)
    stuck.status = SyncRun.Status.RUNNING
    stuck.save()
    # E.g. the worker was killed during the sync.
    ProcrastinateJob.objects.filter(id=stuck.job_id).update(status="failed")

    second = start_sync(linked)

    stuck.refresh_from_db()
    assert second != stuck
    assert stuck.status == SyncRun.Status.FAILED
    assert stuck.errors == [
        {"game": None, "reason": "The background worker stopped during the sync."}
    ]


# ---------------------------------------------------------------- Lichess


def lichess_answers(sites: FakeSites) -> None:
    content = (FIXTURES / "lichess_games.ndjson").read_bytes()
    sites.handler = lambda request: httpx.Response(200, content=content)


def test_a_first_lichess_sync_stores_all_games(alice: User, sites: FakeSites) -> None:
    alice.player_names = ["alice64"]
    alice.save()
    linked = account(alice)
    lichess_answers(sites)

    run = synced(linked)

    assert run.status == SyncRun.Status.DONE
    assert (run.games_imported, run.games_duplicate, run.games_failed) == (2, 0, 0)
    assert run.started_at is not None
    assert run.finished_at is not None
    games = Game.objects.filter(user=alice).order_by("date")
    assert [(g.source, g.source_id, g.user_color) for g in games] == [
        ("lichess", "FdVI4HR4", "black"),
        ("lichess", "IyFe2k8U", "black"),
    ]
    assert "since" not in sites.requests[0].url.params
    # The cursor: when the newest stored game began.
    assert linked.synced_until == datetime(2024, 3, 24, 17, 30, 10, 255000, tzinfo=UTC)


def test_the_next_lichess_sync_starts_after_the_newest_game(alice: User, sites: FakeSites) -> None:
    linked = account(alice)
    lichess_answers(sites)
    synced(linked)
    cursor = linked.synced_until
    assert cursor is not None

    run = synced(linked)  # the fake site sends the same games again

    expected_since = int((cursor + timedelta(milliseconds=1)).timestamp() * 1000)
    assert sites.requests[1].url.params["since"] == str(expected_since)
    assert (run.games_imported, run.games_duplicate) == (0, 2)
    assert linked.synced_until == cursor


def test_a_broken_game_is_counted_and_the_others_stored(alice: User, sites: FakeSites) -> None:
    content = (FIXTURES / "lichess_games.ndjson").read_text()
    broken = content.replace("1. d4", "1. d5", 1)  # the first game's first move is illegal
    sites.handler = lambda request: httpx.Response(200, text=broken)

    run = synced(account(alice))

    assert (run.games_imported, run.games_failed) == (1, 1)
    assert run.errors[0]["game"] == "FdVI4HR4"
    assert "illegal san" in run.errors[0]["reason"]


def test_an_unknown_player_fails_the_sync_with_a_reason(alice: User, sites: FakeSites) -> None:
    sites.handler = lambda request: httpx.Response(404)

    run = synced(account(alice, username="nobody"))  # doesn't raise: nothing to fix in the code

    assert run.status == SyncRun.Status.FAILED
    assert run.errors == [{"game": None, "reason": 'There is no player called "nobody".'}]


def test_an_unexpected_error_fails_the_sync_and_reaches_the_worker(
    alice: User, sites: FakeSites
) -> None:
    sites.handler = lambda request: httpx.Response(200, text='{"id": "abc"}\n')  # no PGN
    linked = account(alice)
    run = start_sync(linked)

    with pytest.raises(KeyError):
        run_sync(sync_run_id=run.pk)

    run.refresh_from_db()
    assert run.status == SyncRun.Status.FAILED
    assert run.finished_at is not None


# ---------------------------------------------------------------- Chess.com


@pytest.fixture
def march_2024(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2024, 3, 15, 12, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: now)


def chesscom_answers(sites: FakeSites) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/archives"):
            return httpx.Response(200, content=(FIXTURES / "chesscom_archives.json").read_bytes())
        if request.url.path.endswith("/2024/01"):
            return httpx.Response(200, content=(FIXTURES / "chesscom_2024_01.json").read_bytes())
        return httpx.Response(200, json={"games": []})

    sites.handler = handler


@pytest.mark.usefixtures("march_2024")
def test_a_first_chesscom_sync_fetches_every_month(alice: User, sites: FakeSites) -> None:
    linked = account(alice, platform=CHESSCOM, username="Alice64")
    chesscom_answers(sites)

    run = synced(linked)

    assert run.status == SyncRun.Status.DONE
    # The fixture's Chess960 game is skipped, not counted as broken.
    assert (run.games_imported, run.games_failed) == (2, 0)
    assert sorted(Game.objects.values_list("source_id", flat=True)) == [
        "live/100455804797",
        "live/97872578329",
    ]
    assert sites.paths == [
        "/pub/player/alice64/games/archives",
        "/pub/player/alice64/games/2024/01",
        "/pub/player/alice64/games/2024/02",
        "/pub/player/alice64/games/2024/03",
    ]
    # January and February are over; March may still get games.
    assert linked.synced_until == datetime(2024, 3, 1, tzinfo=UTC)


@pytest.mark.usefixtures("march_2024")
def test_the_next_chesscom_sync_fetches_only_open_months(alice: User, sites: FakeSites) -> None:
    linked = account(alice, platform=CHESSCOM, username="Alice64")
    chesscom_answers(sites)
    synced(linked)
    sites.requests.clear()

    synced(linked)

    assert sites.paths == [
        "/pub/player/alice64/games/archives",
        "/pub/player/alice64/games/2024/03",
    ]


def test_a_december_archive_moves_the_cursor_to_january(
    alice: User, sites: FakeSites, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(timezone, "now", lambda: datetime(2025, 2, 1, tzinfo=UTC))
    archives = {"archives": ["https://api.chess.com/pub/player/alice64/games/2024/12"]}
    sites.handler = lambda request: httpx.Response(
        200, json=archives if request.url.path.endswith("/archives") else {"games": []}
    )
    linked = account(alice, platform=CHESSCOM)

    synced(linked)

    assert linked.synced_until == datetime(2025, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------- user agent


def test_requests_carry_the_operators_contact_if_set(
    alice: User, sites: FakeSites, settings: Settings
) -> None:
    settings.SYNC_CONTACT = "admin@example.org"
    lichess_answers(sites)

    synced(account(alice))

    assert sites.requests[0].headers["User-Agent"] == (
        "Home-Rank (+https://github.com/januhrhammer/Home-Rank) admin@example.org"
    )


def test_without_a_contact_the_user_agent_names_the_app(settings: Settings) -> None:
    settings.SYNC_CONTACT = ""

    assert services.user_agent() == "Home-Rank (+https://github.com/januhrhammer/Home-Rank)"


def test_the_job_runs_the_sync(alice: User, sites: FakeSites) -> None:
    lichess_answers(sites)
    run = start_sync(account(alice))

    tasks.sync_account(sync_run_id=run.pk)

    run.refresh_from_db()
    assert run.status == SyncRun.Status.DONE
