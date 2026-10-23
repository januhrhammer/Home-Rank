"""Background jobs of the training app, run by the Procrastinate worker (`just worker`)."""

from procrastinate.contrib.django import app

from homerank.training import services


@app.task
def scan_game(game_id: int) -> None:
    """Search an analysed game for puzzles; services.queue_puzzle_scans queues it."""
    services.scan_game(game_id=game_id)


@app.periodic(cron="*/5 * * * *")  # every 5 minutes
@app.task
def queue_puzzle_scans(timestamp: int) -> None:
    """Queue searches of newly analysed games. Procrastinate passes periodic tasks the time
    they were scheduled for (unused here)."""
    services.queue_puzzle_scans()
