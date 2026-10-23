"""The play API: games against bots."""

from http import HTTPStatus
from typing import Any

import chess
import pytest
from django.test import Client

from homerank.accounts.models import User
from homerank.games.models import Game
from homerank.play.models import BotGame

pytestmark = [pytest.mark.django_db, pytest.mark.maia]

AS_JSON = "application/json"
URL = "/api/v1/play"
BACK_RANK = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"  # White mates with Rd8


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice", player_names=["alice64"])


@pytest.fixture
def alice_client(client: Client, alice: User) -> Client:
    client.force_login(alice)
    return client


def post(client: Client, url: str, data: dict[str, Any] | None = None) -> Any:
    return client.post(url, data or {}, content_type=AS_JSON)


def start(client: Client, **fields: Any) -> Any:
    return post(
        client,
        f"{URL}/games",
        {"user_color": "white", "opponent": "maia", "opponent_elo": 1500, **fields},
    )


def test_the_opponents_and_their_ratings(alice_client: Client) -> None:
    assert alice_client.get(f"{URL}/opponents").json() == [
        {"opponent": "maia", "min_elo": 800, "max_elo": 2400},
        {"opponent": "stockfish", "min_elo": 1320, "max_elo": 3190},
    ]


def test_start_a_game_and_play_a_move(alice_client: Client) -> None:
    started = start(alice_client, start_label="From the start")
    game_id = started.json()["id"]

    played = post(alice_client, f"{URL}/games/{game_id}/moves", {"move_uci": "e2e4"})

    assert started.status_code == HTTPStatus.CREATED
    assert started.json() | {"created_at": None} == {
        "id": game_id,
        "start_fen": chess.STARTING_FEN,
        "start_label": "From the start",
        "user_color": "white",
        "opponent": "maia",
        "opponent_elo": 1500,
        "opponent_name": "Maia 1500",
        "moves": [],
        "fen": chess.STARTING_FEN,
        "status": "playing",
        "result": "",
        "termination": None,
        "clock": None,
        "created_at": None,
        "finished_at": None,
        "saved_game_id": None,
    }
    assert played.status_code == HTTPStatus.OK
    moves = played.json()["moves"]
    board = chess.Board()
    for move in moves:
        board.push_uci(move)
    assert moves[0] == "e2e4"
    assert len(moves) == len(board.move_stack)
    assert played.json()["fen"] == board.fen()


def test_a_timed_game_shows_both_clocks(alice_client: Client) -> None:
    game = start(alice_client, clock={"base_seconds": 300, "increment_seconds": 3}).json()

    clock = game["clock"]
    five_minutes = 300_000
    assert (clock["base_ms"], clock["increment_ms"]) == (five_minutes, 3_000)
    assert clock["black_ms"] == five_minutes
    assert five_minutes - 1000 < clock["white_ms"] <= five_minutes  # running since the start


def test_mate_take_back_resign_and_save(alice_client: Client) -> None:
    game_id = start(alice_client, start_fen=BACK_RANK).json()["id"]
    mated = post(alice_client, f"{URL}/games/{game_id}/moves", {"move_uci": "d1d8"}).json()
    saved = post(alice_client, f"{URL}/games/{game_id}/save").json()
    again = alice_client.get(f"{URL}/games/{game_id}").json()

    assert (mated["status"], mated["result"], mated["termination"]) == (
        "finished",
        "1-0",
        "checkmate",
    )
    assert Game.objects.get(pk=saved["game_id"]).user.username == "alice"
    assert again["saved_game_id"] == saved["game_id"]

    other_id = start(alice_client).json()["id"]
    post(alice_client, f"{URL}/games/{other_id}/moves", {"move_uci": "e2e4"})
    taken_back = post(alice_client, f"{URL}/games/{other_id}/take-back").json()
    resigned = post(alice_client, f"{URL}/games/{other_id}/resign").json()
    assert taken_back["moves"] == []
    assert (resigned["result"], resigned["termination"]) == ("0-1", "resignation")


def test_mistakes_get_a_problem_detail(alice_client: Client) -> None:
    game_id = start(alice_client).json()["id"]

    illegal = post(alice_client, f"{URL}/games/{game_id}/moves", {"move_uci": "e2e5"})
    nothing = post(alice_client, f"{URL}/games/{game_id}/take-back")
    weak = start(alice_client, opponent_elo=500)
    no_position = start(alice_client, start_fen="8/8/8/8/8/8/8/8 w - - 0 1")
    long_clock = start(alice_client, clock={"base_seconds": 99_999, "increment_seconds": 0})

    assert illegal.status_code == HTTPStatus.BAD_REQUEST
    assert illegal.json()["detail"] == "This move isn't legal in this position."
    assert nothing.status_code == HTTPStatus.CONFLICT
    assert weak.status_code == HTTPStatus.BAD_REQUEST
    assert no_position.status_code == HTTPStatus.BAD_REQUEST
    assert long_clock.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_list_and_delete(alice_client: Client) -> None:
    first = start(alice_client).json()["id"]
    second = start(alice_client, user_color="black").json()["id"]

    listed = [game["id"] for game in alice_client.get(f"{URL}/games").json()]
    deleted = alice_client.delete(f"{URL}/games/{first}")

    assert listed == [second, first]  # newest first
    assert deleted.status_code == HTTPStatus.NO_CONTENT
    assert list(BotGame.objects.values_list("pk", flat=True)) == [second]


def test_someone_elses_games_are_not_found(alice_client: Client, client: Client) -> None:
    game_id = start(alice_client).json()["id"]
    bob = User.objects.create_user(username="bob")
    client.force_login(bob)

    responses = [
        client.get(f"{URL}/games/{game_id}"),
        post(client, f"{URL}/games/{game_id}/moves", {"move_uci": "e2e4"}),
        post(client, f"{URL}/games/{game_id}/take-back"),
        post(client, f"{URL}/games/{game_id}/resign"),
        post(client, f"{URL}/games/{game_id}/save"),
        client.delete(f"{URL}/games/{game_id}"),
    ]

    assert [response.status_code for response in responses] == [HTTPStatus.NOT_FOUND] * 6
    assert client.get(f"{URL}/games").json() == []
    game = BotGame.objects.get(pk=game_id)
    assert (game.moves, game.status) == ([], "playing")
    assert not Game.objects.filter(user=bob).exists()


def test_logged_out_visitors_get_nothing(client: Client) -> None:
    assert client.get(f"{URL}/games").status_code == HTTPStatus.UNAUTHORIZED
    assert start(client).status_code == HTTPStatus.UNAUTHORIZED
