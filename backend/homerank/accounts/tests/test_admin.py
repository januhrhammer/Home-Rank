from http import HTTPStatus

import pytest
from django.test import Client
from django.urls import reverse

from homerank.accounts.models import User


def test_admin_requires_login(client: Client) -> None:
    response = client.get(reverse("admin:index"))

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"].startswith(reverse("admin:login"))


@pytest.mark.django_db
def test_regular_users_cannot_enter_the_admin(client: Client) -> None:
    client.force_login(User.objects.create_user(username="alice"))

    response = client.get(reverse("admin:index"))

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"].startswith(reverse("admin:login"))


def test_staff_can_see_users_in_the_admin(admin_client: Client) -> None:
    User.objects.create_user(username="alice")

    response = admin_client.get(reverse("admin:accounts_user_changelist"))

    assert response.status_code == HTTPStatus.OK
    assert "alice" in response.content.decode()


def test_staff_can_set_a_users_player_names(admin_client: Client) -> None:
    alice = User.objects.create_user(username="alice")
    page = reverse("admin:accounts_user_change", args=[alice.pk])

    response = admin_client.post(
        page,
        {
            "username": "alice",
            "date_joined_0": "2026-10-22",
            "date_joined_1": "12:00:00",
            "is_active": "on",
            "player_names": "Uhrhammer, Jan\r\njanuhrhammer",
        },
    )

    assert response.status_code == HTTPStatus.FOUND, response.context["adminform"].form.errors
    alice.refresh_from_db()
    assert alice.player_names == ["Uhrhammer, Jan", "januhrhammer"]
