"""Scheduled syncs: every enabled account is synced again after SYNC_INTERVAL_HOURS."""

from datetime import timedelta

import pytest
from django.utils import timezone
from pytest_django import Settings

from homerank.accounts.models import User
from homerank.sync import tasks
from homerank.sync.models import LinkedAccount, SyncRun
from homerank.sync.services import queue_due_syncs

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def every_six_hours(settings: Settings) -> None:
    settings.SYNC_INTERVAL_HOURS = 6


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


def account(user: User, username: str, *, enabled: bool = True) -> LinkedAccount:
    return LinkedAccount.objects.create(
        user=user, platform="lichess", username=username, enabled=enabled
    )


def synced_hours_ago(linked: LinkedAccount, hours: float) -> None:
    run = SyncRun.objects.create(account=linked, status="done")
    SyncRun.objects.filter(pk=run.pk).update(created_at=timezone.now() - timedelta(hours=hours))


def queued_accounts() -> set[str]:
    runs = SyncRun.objects.filter(status="queued").select_related("account")
    return {run.account.username for run in runs}


def test_queues_accounts_never_synced_or_synced_long_enough_ago(alice: User) -> None:
    account(alice, "never")
    synced_hours_ago(account(alice, "long_ago"), 7)
    synced_hours_ago(account(alice, "recently"), 5)
    account(alice, "disabled", enabled=False)

    assert queue_due_syncs() == len({"never", "long_ago"})

    assert queued_accounts() == {"never", "long_ago"}


def test_queues_nothing_twice(alice: User) -> None:
    account(alice, "never")
    queue_due_syncs()

    assert queue_due_syncs() == 0
    assert SyncRun.objects.count() == 1


def test_an_interval_of_zero_turns_the_schedule_off(alice: User, settings: Settings) -> None:
    settings.SYNC_INTERVAL_HOURS = 0
    account(alice, "never")

    assert queue_due_syncs() == 0
    assert not SyncRun.objects.exists()


def test_the_periodic_job_queues_due_syncs(alice: User) -> None:
    account(alice, "never")

    tasks.queue_scheduled_syncs(timestamp=0)

    assert queued_accounts() == {"never"}
