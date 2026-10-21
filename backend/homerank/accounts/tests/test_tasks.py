from datetime import timedelta

import pytest
from django.contrib.sessions.models import Session
from django.utils import timezone
from procrastinate.contrib.django import app
from procrastinate.testing import InMemoryConnector

from homerank.accounts.tasks import clear_expired_sessions


def make_session(key: str, expires_in: timedelta) -> None:
    Session.objects.create(
        session_key=key, session_data="", expire_date=timezone.now() + expires_in
    )


@pytest.mark.django_db
def test_clear_expired_sessions_keeps_current_ones() -> None:
    make_session("expired", timedelta(days=-1))
    make_session("current", timedelta(days=1))

    clear_expired_sessions(timestamp=0)

    assert list(Session.objects.values_list("session_key", flat=True)) == ["current"]


# transaction=True: the worker runs the task in another thread with its own database connection,
# which only sees committed data.
@pytest.mark.django_db(transaction=True)
def test_the_worker_finds_and_runs_the_task() -> None:
    make_session("expired", timedelta(days=-1))

    with app.replace_connector(InMemoryConnector()) as in_memory_app:
        # Queue the job by task name, as it is stored in the database, and let a worker run it.
        task = in_memory_app.configure_task("homerank.accounts.tasks.clear_expired_sessions")
        task.defer(timestamp=0)
        in_memory_app.run_worker(wait=False, install_signal_handlers=False, listen_notify=False)

    assert not Session.objects.exists()
