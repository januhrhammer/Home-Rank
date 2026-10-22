from http import HTTPStatus

from django.test import Client
from django.urls import reverse

from homerank.accounts.models import User
from homerank.games.models import ImportRun


def test_staff_can_see_imports_but_not_add_them(admin_client: Client) -> None:
    alice = User.objects.create_user(username="alice")
    ImportRun.objects.create(user=alice, file_name="club-games.pgn", file_size=1234)

    response = admin_client.get(reverse("admin:games_importrun_changelist"))

    assert response.status_code == HTTPStatus.OK
    assert "club-games.pgn" in response.content.decode()
    add_page = admin_client.get(reverse("admin:games_importrun_add"))
    assert add_page.status_code == HTTPStatus.FORBIDDEN
