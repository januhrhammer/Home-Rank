import threading

import psycopg
import pytest
from django.core.management import call_command
from django.db import connection, connections

from homerank.core.management.commands.migrate_with_lock import MIGRATION_LOCK_ID


@pytest.mark.django_db(transaction=True)
def test_waits_while_another_container_is_migrating() -> None:
    # The other container: a separate connection to the same database, holding the lock.
    other_container = psycopg.connect(**connection.get_connection_params())
    other_container.execute("SELECT pg_advisory_lock(%s)", [MIGRATION_LOCK_ID])

    finished = threading.Event()

    def migrate() -> None:
        try:
            call_command("migrate_with_lock", verbosity=0)
        finally:
            connections.close_all()  # this thread's own database connection
            finished.set()

    thread = threading.Thread(target=migrate)
    thread.start()
    try:
        assert not finished.wait(timeout=1), "migrated although the lock was taken"

        other_container.execute("SELECT pg_advisory_unlock(%s)", [MIGRATION_LOCK_ID])

        assert finished.wait(timeout=10), "still waiting after the lock was released"
    finally:
        other_container.close()  # releases the lock if the test failed while holding it
        thread.join()
