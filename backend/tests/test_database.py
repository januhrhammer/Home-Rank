"""The test suite runs against a real PostgreSQL, never SQLite.

Bulk imports (COPY), table partitioning and the job queue (LISTEN/NOTIFY) all rely on
PostgreSQL, so tests passing on another database would prove little.
"""

import pytest
from django.db import connection


@pytest.mark.django_db
def test_runs_against_postgres() -> None:
    assert connection.vendor == "postgresql"
