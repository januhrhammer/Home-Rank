"""The sync API: linking accounts, syncing them, and seeing how their syncs went."""

from http import HTTPStatus
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from homerank.accounts.models import User
from homerank.sync.models import LinkedAccount, SyncRun

pytestmark = pytest.mark.django_db

AS_JSON = "application/json"


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


@pytest.fixture
def bob() -> User:
    return User.objects.create_user(username="bob")


@pytest.fixture
def alice_client(client: Client, alice: User) -> Client:
    client.force_login(alice)
    return client


def link(client: Client, platform: str = "lichess", username: str = "alice64") -> Any:
    data = {"platform": platform, "username": username}
    return client.post("/api/v1/sync/accounts", data, content_type=AS_JSON)


def test_links_an_account_and_queues_its_first_sync(alice_client: Client, alice: User) -> None:
    response = link(alice_client, username="  alice64 ")

    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert (body["platform"], body["username"], body["enabled"]) == ("lichess", "alice64", True)
    assert body["synced_until"] is None
    assert body["last_run"]["status"] == "queued"
    alice.refresh_from_db()
    assert alice.player_names == ["alice64"]


@pytest.mark.parametrize("username", ["", "a", "x" * 51, "alice 64", "../alice", "alice?x=1"])
def test_refuses_impossible_usernames(alice_client: Client, username: str) -> None:
    assert link(alice_client, username=username).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_refuses_unknown_platforms(alice_client: Client) -> None:
    response = link(alice_client, platform="chess24")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_an_account_is_linked_once(alice_client: Client) -> None:
    link(alice_client, username="alice64")

    response = link(alice_client, username="ALICE64")

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["detail"] == 'You have already linked the Lichess account "ALICE64".'


def test_lists_accounts_with_their_newest_sync(alice_client: Client, alice: User) -> None:
    lichess = LinkedAccount.objects.create(user=alice, platform="lichess", username="alice64")
    LinkedAccount.objects.create(user=alice, platform="chesscom", username="Alice64")
    SyncRun.objects.create(account=lichess, status="done", games_imported=5)
    SyncRun.objects.create(account=lichess, status="failed", errors=[{"game": None, "reason": "x"}])

    page = alice_client.get("/api/v1/sync/accounts").json()

    assert page["total"] == len(page["items"])
    assert [(a["platform"], a["last_run"] and a["last_run"]["status"]) for a in page["items"]] == [
        ("chesscom", None),
        ("lichess", "failed"),
    ]
    assert page["items"][1]["last_run"]["errors"] == [{"game": None, "reason": "x"}]


def test_listing_takes_the_same_queries_for_any_number_of_accounts(
    alice_client: Client, alice: User
) -> None:
    def queries() -> int:
        with CaptureQueriesContext(connection) as captured:
            alice_client.get("/api/v1/sync/accounts")
        return len(captured)

    for name in ("one", "two"):
        account = LinkedAccount.objects.create(user=alice, platform="lichess", username=name)
        SyncRun.objects.create(account=account)
    two = queries()
    for name in ("three", "four"):
        account = LinkedAccount.objects.create(user=alice, platform="lichess", username=name)
        SyncRun.objects.create(account=account)

    assert queries() == two


def test_turns_the_scheduled_sync_off(alice_client: Client, alice: User) -> None:
    account = LinkedAccount.objects.create(user=alice, platform="lichess", username="alice64")

    response = alice_client.patch(
        f"/api/v1/sync/accounts/{account.pk}", {"enabled": False}, content_type=AS_JSON
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["enabled"] is False
    account.refresh_from_db()
    assert account.enabled is False


def test_unlinks_an_account(alice_client: Client, alice: User) -> None:
    account = LinkedAccount.objects.create(user=alice, platform="lichess", username="alice64")

    response = alice_client.delete(f"/api/v1/sync/accounts/{account.pk}")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert not LinkedAccount.objects.exists()


def test_syncs_now_and_returns_the_queued_sync(alice_client: Client, alice: User) -> None:
    account = LinkedAccount.objects.create(user=alice, platform="lichess", username="alice64")
    url = f"/api/v1/sync/accounts/{account.pk}/sync"

    first = alice_client.post(url)
    again = alice_client.post(url)

    assert first.status_code == again.status_code == HTTPStatus.ACCEPTED
    assert first.json()["status"] == "queued"
    assert again.json()["id"] == first.json()["id"]  # no second sync while one is queued
    detail = alice_client.get(f"/api/v1/sync/accounts/{account.pk}").json()
    assert detail["last_run"]["id"] == first.json()["id"]


# Isolation: users only ever see and change their own linked accounts.


def test_lists_only_your_own(alice_client: Client, alice: User, bob: User) -> None:
    LinkedAccount.objects.create(user=alice, platform="lichess", username="mine")
    LinkedAccount.objects.create(user=bob, platform="lichess", username="bobs")

    page = alice_client.get("/api/v1/sync/accounts").json()

    assert [item["username"] for item in page["items"]] == ["mine"]


def test_someone_elses_is_not_found(alice_client: Client, bob: User) -> None:
    bobs = LinkedAccount.objects.create(user=bob, platform="lichess", username="bobs")
    url = f"/api/v1/sync/accounts/{bobs.pk}"

    responses = [
        alice_client.get(url),
        alice_client.patch(url, {"enabled": False}, content_type=AS_JSON),
        alice_client.post(f"{url}/sync"),
        alice_client.delete(url),
    ]

    assert [r.status_code for r in responses] == [HTTPStatus.NOT_FOUND] * len(responses)
    bobs.refresh_from_db()
    assert bobs.enabled is True
    assert not SyncRun.objects.exists()


def test_the_same_account_may_be_linked_by_another_user(alice_client: Client, bob: User) -> None:
    LinkedAccount.objects.create(user=bob, platform="lichess", username="alice64")

    assert link(alice_client, username="alice64").status_code == HTTPStatus.CREATED


def test_requires_login(client: Client) -> None:
    assert client.get("/api/v1/sync/accounts").status_code == HTTPStatus.UNAUTHORIZED
    assert link(client).status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}
