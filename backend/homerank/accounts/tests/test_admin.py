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
