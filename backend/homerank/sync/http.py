"""Requests to the chess sites, shared by the Lichess and Chess.com clients.

Like the clients, this module doesn't use Django: the sync service passes in what it needs.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import httpx

# Both sites ask clients to wait at least a minute after HTTP 429 (Too Many Requests).
MIN_WAIT_SECONDS = 60
# Requests tried in all when a site keeps answering 429.
MAX_ATTEMPTS = 3
# Generous, because a site may take a while to start streaming a long game export.
TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class RemoteGame:
    """A game as a chess site sent it."""

    id: str  # the site's id for the game; stored as Game.source_id
    pgn: str
    played_at: datetime  # when it began (Lichess) or ended (Chess.com)


class PlayerNotFoundError(Exception):
    def __init__(self, username: str) -> None:
        super().__init__(f'There is no player called "{username}".')


class RateLimitedError(Exception):
    def __init__(self) -> None:
        super().__init__("The site keeps asking us to slow down (HTTP 429). Try again later.")


def new_client(*, user_agent: str) -> httpx.Client:
    """A client for one sync: requests one at a time, saying who is asking."""
    return httpx.Client(headers={"User-Agent": user_agent}, timeout=TIMEOUT_SECONDS)


def send(
    client: httpx.Client,
    request: httpx.Request,
    *,
    stream: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """Send the request, waiting and trying again while the site answers 429.

    With stream=True the caller reads the body as it arrives and must close the response.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = client.send(request, stream=stream)
        if response.status_code != httpx.codes.TOO_MANY_REQUESTS:
            return response
        response.close()
        if attempt < MAX_ATTEMPTS:
            sleep(max(MIN_WAIT_SECONDS, _retry_after(response)))
    raise RateLimitedError


def _retry_after(response: httpx.Response) -> int:
    """The seconds the site asks us to wait, if it says so as a number (0 if it doesn't)."""
    try:
        return int(response.headers.get("Retry-After", ""))
    except ValueError:
        return 0
