"""`manage.py migrate_with_lock`: apply migrations, one container at a time.

The web container migrates the database whenever it starts. If several containers start at
once, they must not apply the same migrations side by side. A PostgreSQL advisory lock is held
by one database connection at a time, so every other container waits here until the first is
done, and then finds nothing left to apply.
"""

from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

# Advisory locks are identified by a number; this one is reserved for migrations.
MIGRATION_LOCK_ID = 7_384_201


class Command(BaseCommand):
    help = "Apply database migrations, waiting while another container is applying them."

    def handle(self, *args: Any, **options: Any) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [MIGRATION_LOCK_ID])
            try:
                call_command("migrate", interactive=False, verbosity=options["verbosity"])
            finally:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [MIGRATION_LOCK_ID])
