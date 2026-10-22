from http import HTTPStatus
from typing import Any

import pytest
from django.test import Client
from procrastinate.contrib.django.models import ProcrastinateJob

from homerank.accounts.models import User

SETTINGS = "/api/v1/settings"

pytestmark = pytest.mark.django_db


@pytest.fixture
def jan() -> User:
    return User.objects.create_user(username="jan", player_names=["Uhrhammer, Jan"])


@pytest.fixture
def jan_client(client: Client, jan: User) -> Client:
    client.force_login(jan)
    return client


def change(client: Client, **changes: Any) -> Any:
    return client.patch(SETTINGS, changes, content_type="application/json")


def test_shows_the_player_names(jan_client: Client) -> None:
    response = jan_client.get(SETTINGS)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"player_names": ["Uhrhammer, Jan"]}


def test_requires_login(client: Client) -> None:
    assert client.get(SETTINGS).status_code == HTTPStatus.UNAUTHORIZED
    assert change(client, player_names=[]).status_code == HTTPStatus.UNAUTHORIZED


def test_new_names_are_saved_and_the_games_updated(jan_client: Client, jan: User) -> None:
    response = change(jan_client, player_names=["Uhrhammer, Jan", "januhrhammer"])

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"player_names": ["Uhrhammer, Jan", "januhrhammer"]}
    jan.refresh_from_db()
    assert jan.player_names == ["Uhrhammer, Jan", "januhrhammer"]
    job = ProcrastinateJob.objects.get()
    assert job.task_name == "homerank.games.tasks.recompute_user_colors"
    assert job.args == {"user_id": jan.pk}
    assert job.lock == f"user-{jan.pk}"  # never at the same time as one of jan's imports


def test_names_are_tidied(jan_client: Client) -> None:
    response = change(
        jan_client, player_names=["  januhrhammer ", "", "Uhrhammer,   Jan", "uhrhammer, jan"]
    )

    # Spaces trimmed and collapsed, empty lines and spelling variants of a name dropped.
    assert response.json() == {"player_names": ["januhrhammer", "Uhrhammer, Jan"]}


def test_the_same_names_change_nothing(jan_client: Client) -> None:
    response = change(jan_client, player_names=["Uhrhammer, Jan"])

    assert response.status_code == HTTPStatus.OK
    assert not ProcrastinateJob.objects.exists()


def test_settings_left_out_stay(jan_client: Client, jan: User) -> None:
    response = change(jan_client)

    assert response.json() == {"player_names": ["Uhrhammer, Jan"]}
    assert not ProcrastinateJob.objects.exists()


@pytest.mark.parametrize(
    "names",
    [["x" * 101], [f"name {number}" for number in range(21)]],
    ids=["a name over 100 characters", "more than 20 names"],
)
def test_refuses_too_much(jan_client: Client, jan: User, names: list[str]) -> None:
    response = change(jan_client, player_names=names)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    jan.refresh_from_db()
    assert jan.player_names == ["Uhrhammer, Jan"]


def test_changes_only_the_users_own_settings(jan_client: Client) -> None:
    other = User.objects.create_user(username="other", player_names=["Other"])

    change(jan_client, player_names=["januhrhammer"])

    other.refresh_from_db()
    assert other.player_names == ["Other"]


def test_requires_the_csrf_token(jan: User) -> None:
    client = Client(enforce_csrf_checks=True)
    client.force_login(jan)

    response = change(client, player_names=["januhrhammer"])

    assert response.status_code == HTTPStatus.FORBIDDEN
    jan.refresh_from_db()
    assert jan.player_names == ["Uhrhammer, Jan"]
