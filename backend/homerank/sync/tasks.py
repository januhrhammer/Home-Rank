"""Background jobs of the sync app, run by the Procrastinate worker (`just worker`)."""

from procrastinate.contrib.django import app

from homerank.sync import services


@app.task
def sync_account(sync_run_id: int) -> None:
    """Fetch a linked account's new games; services.start_sync queues it."""
    services.run_sync(sync_run_id=sync_run_id)


@app.periodic(cron="*/15 * * * *")  # every 15 minutes
@app.task
def queue_scheduled_syncs(timestamp: int) -> None:
    """Queue the syncs that are due. Procrastinate passes periodic tasks the time they were
    scheduled for (unused here)."""
    services.queue_due_syncs()
