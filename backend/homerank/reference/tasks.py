"""Background jobs of the reference app, run by the Procrastinate worker (`just worker`)."""

from procrastinate.contrib.django import app

from homerank.reference import services


@app.task
def import_reference(import_id: int) -> None:
    """Import PGN files into a reference database; services.start_import queues it."""
    services.run_import(import_id=import_id)
