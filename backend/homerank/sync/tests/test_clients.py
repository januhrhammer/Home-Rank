"""The Lichess and Chess.com clients, against answers recorded from the real sites.

The fixtures are trimmed copies of real answers with made-up player names. No test makes a
real request: every client here talks to an httpx.MockTransport.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from homerank.sync import chesscom, lichess
from homerank.sync.http import PlayerNotFoundError, RateLimitedError, new_client

FIXTURES = Path(__file__).parent / "fixtures"

Handler = Callable[[httpx.Request], httpx.Response]


def client(handler: Handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class Sleeps:
    """Records how long the client would have waited, instead of waiting."""

    def __init__(self) -> None:
        self.seconds: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


# ---------------------------------------------------------------- Lichess


def test_lichess_games_arrive_oldest_first_with_their_pgn() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=fixture("lichess_games.ndjson"))

    games = list(lichess.games(client(handler), "alice64", since=None))

    assert [game.id for game in games] == ["FdVI4HR4", "IyFe2k8U"]
    assert games[0].played_at == datetime(2023, 12, 22, 17, 0, 3, 288000, tzinfo=UTC)
    assert games[0].pgn.startswith('[Event "Rated blitz game"]')
    assert '[Black "alice64"]' in games[0].pgn
    (request,) = requests
    assert request.url.path == "/api/games/user/alice64"
    assert request.url.params["sort"] == "dateAsc"
    assert "since" not in request.url.params
    assert "chess960" not in request.url.params["perfType"]
    assert request.headers["Accept"] == "application/x-ndjson"


def test_lichess_games_since_a_time_are_asked_for_in_milliseconds() -> None:
    params: list[httpx.QueryParams] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params.append(request.url.params)
        return httpx.Response(200, content=b"")

    since = datetime(2024, 1, 1, tzinfo=UTC)
    assert list(lichess.games(client(handler), "alice64", since=since)) == []

    assert params[0]["since"] == "1704067200000"


def test_lichess_reports_an_unknown_player() -> None:
    lichess_404 = client(lambda request: httpx.Response(404, text="<!DOCTYPE html>"))

    with pytest.raises(PlayerNotFoundError, match='no player called "nobody"'):
        list(lichess.games(lichess_404, "nobody", since=None))


def test_lichess_usernames_cant_change_the_url() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.raw_path.decode())
        return httpx.Response(200, content=b"")

    list(lichess.games(client(handler), "../account", since=None))

    assert paths[0].startswith("/api/games/user/..%2Faccount?")


# ---------------------------------------------------------------- Chess.com


def test_chesscom_lists_the_months_with_games() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pub/player/alice64/games/archives"
        return httpx.Response(200, content=fixture("chesscom_archives.json"))

    months = chesscom.archives(client(handler), "Alice64")

    assert months == [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)]


def test_chesscom_month_games_are_standard_chess_only() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pub/player/alice64/games/2024/01"
        return httpx.Response(200, content=fixture("chesscom_2024_01.json"))

    games = chesscom.month_games(client(handler), "Alice64", date(2024, 1, 1))

    # The fixture's third game is Chess960.
    assert [game.id for game in games] == ["live/100455804797", "live/97872578329"]
    assert games[1].played_at == datetime(2024, 1, 1, 18, 28, 26, tzinfo=UTC)
    assert '[White "Alice64"]' in games[1].pgn


def test_chesscom_reports_an_unknown_player() -> None:
    chesscom_404 = client(lambda request: httpx.Response(404, json={"code": 0}))

    with pytest.raises(PlayerNotFoundError):
        chesscom.archives(chesscom_404, "nobody")


def test_other_errors_are_raised_as_they_are() -> None:
    broken = client(lambda request: httpx.Response(503))

    with pytest.raises(httpx.HTTPStatusError):
        chesscom.archives(broken, "alice64")
    with pytest.raises(httpx.HTTPStatusError):
        list(lichess.games(broken, "alice64", since=None))


# ---------------------------------------------------------------- rate limits


def answers(*responses: httpx.Response) -> Handler:
    remaining = list(responses)
    return lambda request: remaining.pop(0)


def test_after_429_the_client_waits_at_least_a_minute_and_tries_again() -> None:
    handler = answers(
        httpx.Response(429),
        httpx.Response(429, headers={"Retry-After": "120"}),
        httpx.Response(200, content=fixture("chesscom_archives.json")),
    )
    sleeps = Sleeps()

    months = chesscom.archives(client(handler), "alice64", sleep=sleeps)

    assert months[0] == date(2024, 1, 1)
    assert sleeps.seconds == [60, 120]


def test_a_site_that_keeps_answering_429_stops_the_sync() -> None:
    handler = answers(*(httpx.Response(429, headers={"Retry-After": "soon"}) for _ in range(3)))
    sleeps = Sleeps()

    with pytest.raises(RateLimitedError):
        list(lichess.games(client(handler), "alice64", since=None, sleep=sleeps))
    assert sleeps.seconds == [60, 60]  # no waiting after the last try


def test_requests_say_who_is_asking() -> None:
    agent = "Home-Rank (+https://example.org/source)"
    with new_client(user_agent=agent) as real_client:
        assert real_client.headers["User-Agent"] == agent
