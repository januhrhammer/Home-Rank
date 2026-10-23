"""Fetching a player's games from Lichess's game export API (no login needed).

https://lichess.org/api#tag/Games/operation/apiGamesUser
"""

import json
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from homerank.sync.http import PlayerNotFoundError, RemoteGame, send

API = "https://lichess.org/api"
# Every kind of standard chess game; variants such as Chess960 are left out.
STANDARD_SPEEDS = "ultraBullet,bullet,blitz,rapid,classical,correspondence"


def games(
    client: httpx.Client,
    username: str,
    *,
    since: datetime | None,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[RemoteGame]:
    """The player's finished games that began at or after `since`, the oldest first.

    Lichess streams them as they are found, one JSON object per line; they are yielded the
    same way, so a long history never has to fit into memory.
    """
    params: dict[str, str | int] = {
        "sort": "dateAsc",
        "perfType": STANDARD_SPEEDS,
        "pgnInJson": "true",
        "clocks": "true",
        "opening": "true",
    }
    if since is not None:
        params["since"] = int(since.timestamp() * 1000)  # milliseconds
    request = client.build_request(
        "GET",
        f"{API}/games/user/{quote(username, safe='')}",
        params=params,
        headers={"Accept": "application/x-ndjson"},
    )
    response = send(client, request, stream=True, sleep=sleep)
    try:
        if response.status_code == httpx.codes.NOT_FOUND:
            raise PlayerNotFoundError(username)
        response.raise_for_status()
        for line in response.iter_lines():
            if line.strip():
                yield _game(json.loads(line))
    finally:
        response.close()


def _game(data: dict[str, Any]) -> RemoteGame:
    return RemoteGame(
        id=data["id"],
        pgn=data["pgn"],
        played_at=datetime.fromtimestamp(data["createdAt"] / 1000, tz=UTC),  # milliseconds
    )
