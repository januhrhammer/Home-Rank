from http import HTTPStatus

import pytest
from django.test import Client
from django.urls import reverse

from homerank.accounts.models import User
from homerank.sync.models import LinkedAccount, SyncRun

pytestmark = pytest.mark.django_db


def test_staff_can_see_linked_accounts_and_syncs_but_not_add_them(admin_client: Client) -> None:
    alice = User.objects.create_user(username="alice")
    account = LinkedAccount.objects.create(
        user=alice, platform=LinkedAccount.Platform.LICHESS, username="alice64"
    )
    SyncRun.objects.create(account=account)

    for model in ("linkedaccount", "syncrun"):
        response = admin_client.get(reverse(f"admin:sync_{model}_changelist"))
        assert response.status_code == HTTPStatus.OK
        assert "alice64" in response.content.decode()
        add_page = admin_client.get(reverse(f"admin:sync_{model}_add"))
        assert add_page.status_code == HTTPStatus.FORBIDDEN
