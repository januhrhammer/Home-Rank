"""Background jobs of the analysis app, run by the Procrastinate worker (`just worker`)."""

from procrastinate.contrib.django import app

from homerank.analysis import services


@app.task
def analyse_game(analysis_run_id: int) -> None:
    """Analyse a game with Stockfish; services.start_analysis queues it."""
    services.run_analysis(analysis_run_id=analysis_run_id)


@app.periodic(cron="*/5 * * * *")  # every 5 minutes
@app.task
def queue_auto_analyses(timestamp: int) -> None:
    """Queue analyses of new games. Procrastinate passes periodic tasks the time they were
    scheduled for (unused here)."""
    services.queue_auto_analyses()
