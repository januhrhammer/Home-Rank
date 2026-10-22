"""Background jobs of the sync app, run by the Procrastinate worker (`just worker`)."""

from procrastinate.contrib.django import app

from homerank.sync import services


@app.task
def sync_account(sync_run_id: int) -> None:
    """Fetch a linked account's new games; services.start_sync queues it."""
    services.run_sync(sync_run_id=sync_run_id)
