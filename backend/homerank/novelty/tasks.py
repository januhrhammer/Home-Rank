"""Background jobs of the novelty app, run by the Procrastinate worker (`just worker`)."""

from procrastinate.contrib.django import app

from homerank.novelty import services


@app.task
def novelty_search(search_id: int) -> None:
    """Run a novelty search; services.start_search queues it."""
    services.run_search(search_id)
