"""Background jobs of the games app, run by the Procrastinate worker (`just worker`)."""

from procrastinate.contrib.django import app

from homerank.games import services


@app.task
def import_games(import_run_id: int) -> None:
    """Import an uploaded PGN file; services.start_import queues it."""
    services.run_import(import_run_id=import_run_id)


@app.task
def recompute_user_colors(user_id: int) -> None:
    """Find the user's side in all their games again; changing the player names queues it."""
    services.recompute_user_colors(user_id=user_id)
