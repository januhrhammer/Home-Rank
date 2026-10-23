"""manage.py import_reference: import PGN files into a reference database, from the shell.

For the multi-GB files that are no use to upload: put them into REFERENCE_IMPORT_DIR (/data/import
in Docker) and run, e.g.

    docker compose exec worker python manage.py import_reference lumbra/*.7z --name "Lumbra OTB"

The import runs in this process (not the worker) and can be interrupted: running the same command
again resumes it.
"""

from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from homerank.core.errors import DomainError
from homerank.reference import services
from homerank.reference.models import ReferenceDatabase, ReferenceImport


class Command(BaseCommand):
    help = (
        "Import PGN files (.pgn, .gz, .bz2, .zst, .7z) from REFERENCE_IMPORT_DIR into a "
        "reference database."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("files", nargs="+", help="Paths, relative to REFERENCE_IMPORT_DIR")
        parser.add_argument("--name", required=True, help="The database; created if new")
        parser.add_argument("--description", default="")
        parser.add_argument("--depth", type=int, default=None, help="Plies indexed per game")
        parser.add_argument("--workers", type=int, default=None, help="Parsing processes")

    def handle(self, *args: Any, **options: Any) -> None:
        folder = Path(settings.REFERENCE_IMPORT_DIR).resolve()
        names = [
            str(Path(f).resolve().relative_to(folder)) if Path(f).is_absolute() else f
            for f in options["files"]
        ]
        try:
            paths = [services.import_file_path(name) for name in names]
        except DomainError as error:
            raise CommandError(str(error)) from error
        database = ReferenceDatabase.objects.filter(name=options["name"]).first()
        if database is None:
            database = services.create_database(
                name=options["name"],
                description=options["description"],
                **({"depth": options["depth"]} if options["depth"] else {}),
            )
        estimate = services.estimate(paths, database.depth)
        self.stdout.write(
            f"About {estimate.games:,} games, needing about "
            f"{estimate.disk_bytes / 1e9:.1f} GB of disk space (depth {database.depth})."
        )
        reference_import = self._unfinished(database, paths) or services.create_import(
            database, paths
        )
        services.run_import(import_id=reference_import.pk, workers=options["workers"])
        database.refresh_from_db()
        self.stdout.write(self.style.SUCCESS(f"{database.name}: {database.game_count:,} games."))

    @staticmethod
    def _unfinished(database: ReferenceDatabase, paths: list[Path]) -> ReferenceImport | None:
        """An earlier import of the same files that didn't finish: it resumes."""
        wanted = sorted(str(p) for p in paths)
        for reference_import in database.imports.exclude(status=ReferenceImport.Status.DONE):
            if sorted(f.path for f in reference_import.files.all()) == wanted:
                return reference_import
        return None
