"""Background jobs of the accounts app, run by the Procrastinate worker (`just worker`)."""

from procrastinate.contrib.django import app

from homerank.accounts import services


@app.periodic(cron="30 3 * * *")  # daily at 03:30 UTC
@app.task
def clear_expired_sessions(timestamp: int) -> None:
    """Procrastinate passes periodic tasks the time they were scheduled for (unused here)."""
    services.clear_expired_sessions()
