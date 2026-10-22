"""Fetching a player's games from Chess.com's published-data API (no login needed).

Chess.com keeps one archive of games per month: https://www.chess.com/news/view/published-data-api
"""

import re
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote

import httpx

from homerank.sync.http import PlayerNotFoundError, RemoteGame, send

API = "https://api.chess.com/pub"
# The end of an archive's URL, e.g. ".../games/2024/01".
ARCHIVE_MONTH = re.compile(r"/(\d{4})/(\d{2})$")
# The part of a game's URL that identifies it, e.g. "live/97872578329" or "daily/123".
GAME_ID = re.compile(r"/game/(\w+/\d+)$")


def archives(
    client: httpx.Client, username: str, *, sleep: Callable[[float], None] = time.sleep
) -> list[date]:
    """The months in which the player has games, the oldest first, as their first days."""
    data = _get(client, f"{_player(username)}/games/archives", username, sleep)
    months = []
    for url in data["archives"]:
        if match := ARCHIVE_MONTH.search(url):
            months.append(date(int(match[1]), int(match[2]), 1))
    return sorted(months)


def month_games(
    client: httpx.Client,
    username: str,
    month: date,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> list[RemoteGame]:
    """The player's standard chess games that ended in the month; other rules are skipped."""
    url = f"{_player(username)}/games/{month.year}/{month.month:02}"
    data = _get(client, url, username, sleep)
    games = []
    for game in data["games"]:
        match = GAME_ID.search(game.get("url", ""))
        if game.get("rules") == "chess" and game.get("pgn") and match:
            ended_at = datetime.fromtimestamp(game["end_time"], tz=UTC)
            games.append(RemoteGame(id=match[1], pgn=game["pgn"], played_at=ended_at))
    return games


def _player(username: str) -> str:
    return f"{API}/player/{quote(username.lower(), safe='')}"


def _get(
    client: httpx.Client, url: str, username: str, sleep: Callable[[float], None]
) -> dict[str, Any]:
    response = send(client, client.build_request("GET", url), sleep=sleep)
    if response.status_code == httpx.codes.NOT_FOUND:
        raise PlayerNotFoundError(username)
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data
