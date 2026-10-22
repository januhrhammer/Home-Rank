import datetime
import itertools
from typing import Any

import pytest
from procrastinate.contrib.django import app
from procrastinate.testing import InMemoryConnector

from homerank.accounts.models import User
from homerank.games import services
from homerank.games.models import Game
from homerank.games.services import recompute_user_colors

_hashes = itertools.count()

pytestmark = pytest.mark.django_db


@pytest.fixture
def jan() -> User:
    return User.objects.create_user(username="jan", player_names=["Uhrhammer, Jan"])


def make_game(user: User, white: str, black: str, **fields: Any) -> Game:
    values = {
        "source": Game.Source.PGN,
        "pgn": "1. e4 e5 *\n",
        "result": "*",
        "date": datetime.date(2024, 1, 1),
        "date_pgn": "2024.01.01",
        "time_class": "blitz",
        "ply_count": 2,
        "dedup_hash": f"{next(_hashes):064}",
        **fields,
    }
    return Game.objects.create(user=user, white=white, black=black, **values)


def colors(user: User) -> dict[str, str]:
    """Each of the user's games, by its players, with the user's side in it."""
    return {
        f"{game.white} - {game.black}": game.user_color
        for game in Game.objects.filter(user=user).order_by("id")
    }


def test_finds_the_side_with_the_current_names(jan: User) -> None:
    # Imported before the user added their online name.
    make_game(jan, "januhrhammer", "Ben")
    make_game(jan, "Anna", "januhrhammer")
    make_game(jan, "Uhrhammer, Jan", "Ben", user_color="white")
    jan.player_names = ["Uhrhammer, Jan", "januhrhammer"]
    jan.save()

    recompute_user_colors(user_id=jan.pk)

    assert colors(jan) == {
        "januhrhammer - Ben": "white",
        "Anna - januhrhammer": "black",
        "Uhrhammer, Jan - Ben": "white",
    }


def test_a_removed_name_no_longer_counts(jan: User) -> None:
    make_game(jan, "Uhrhammer, Jan", "Ben", user_color="white")
    jan.player_names = []
    jan.save()

    recompute_user_colors(user_id=jan.pk)

    assert colors(jan) == {"Uhrhammer, Jan - Ben": ""}


def test_leaves_other_users_games_alone(jan: User) -> None:
    other = User.objects.create_user(username="other", player_names=[])
    make_game(other, "Uhrhammer, Jan", "Ben", user_color="black")  # wrong, but not jan's game

    recompute_user_colors(user_id=jan.pk)

    assert colors(other) == {"Uhrhammer, Jan - Ben": "black"}


def test_works_in_batches(jan: User, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "RECOMPUTE_BATCH_SIZE", 2)
    for opponent in ["A", "B", "C", "D", "E"]:
        make_game(jan, "Uhrhammer, Jan", opponent)

    recompute_user_colors(user_id=jan.pk)

    assert set(colors(jan).values()) == {"white"}


# transaction=True: the worker runs the job in another thread with its own database connection,
# which only sees committed data.
@pytest.mark.django_db(transaction=True)
def test_the_worker_runs_the_job(jan: User) -> None:
    make_game(jan, "Uhrhammer, Jan", "Ben")
    with app.replace_connector(InMemoryConnector()) as in_memory_app:
        in_memory_app.configure_task("homerank.games.tasks.recompute_user_colors").defer(
            user_id=jan.pk
        )
        in_memory_app.run_worker(wait=False, install_signal_handlers=False, listen_notify=False)

    assert colors(jan) == {"Uhrhammer, Jan - Ben": "white"}
