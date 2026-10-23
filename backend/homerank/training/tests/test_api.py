"""The training API: the next due puzzle, reviews, the puzzle list and statistics."""

import itertools
from datetime import date, timedelta
from http import HTTPStatus
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from homerank.accounts.models import User
from homerank.games.models import Game
from homerank.training.models import Puzzle, ReviewCard, ReviewLog
from homerank.training.services import _new_card, review

pytestmark = pytest.mark.django_db

AS_JSON = "application/json"
_hashes = itertools.count()


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


def a_puzzle(user: User, *, due_in: timedelta = timedelta(0), **fields: Any) -> Puzzle:
    game_fields = {k: fields.pop(k) for k in ("eco", "opening", "date") if k in fields}
    game = Game.objects.create(
        user=user,
        source=Game.Source.PGN,
        pgn="1. e4 *\n",
        white="alice64",
        black="bob_b",
        result="*",
        date_pgn="2026.10.01",
        time_class="blitz",
        ply_count=1,
        user_color="white",
        dedup_hash=f"{next(_hashes):064}",
        **game_fields,
    )
    values = {
        "kind": "missed",
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "solution": ["e2e4"],
        "themes": ["material"],
        "win_swing": 30.0,
        **fields,
    }
    puzzle = Puzzle.objects.create(user=user, game=game, ply=0, **values)
    card = _new_card(puzzle)
    ReviewCard.objects.filter(pk=card.pk).update(due_at=timezone.now() + due_in)
    return puzzle


def next_puzzle(client: Client, query: str = "") -> Any:
    return client.get(f"/api/v1/training/next{query}").json()


def test_gives_the_puzzle_due_longest(alice_client: Client, alice: User) -> None:
    a_puzzle(alice, due_in=-timedelta(hours=1))
    oldest = a_puzzle(alice, due_in=-timedelta(days=2))
    a_puzzle(alice, due_in=timedelta(days=3))  # not due

    body = next_puzzle(alice_client)

    assert body["due"] == 2  # noqa: PLR2004
    puzzle = body["puzzle"]
    assert puzzle["id"] == oldest.pk
    assert puzzle["card_id"] == oldest.card.pk
    assert puzzle["solution"] == ["e2e4"]
    assert puzzle["game"]["white"] == "alice64"


def test_nothing_due(alice_client: Client, alice: User) -> None:
    a_puzzle(alice, due_in=timedelta(days=1))

    assert next_puzzle(alice_client) == {"puzzle": None, "due": 0}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("?kind=missed", "mine"),
        ("?theme=mateIn2", "mate"),
        ("?eco=B9", "najdorf"),
        ("?opening=najdorf", "najdorf"),
        ("?date_from=2026-06-01", "mate"),
    ],
)
def test_filters_the_puzzles(alice_client: Client, alice: User, query: str, expected: str) -> None:
    puzzles = {
        "mine": a_puzzle(alice, kind="missed", date=date(2026, 1, 1)),
        "mate": a_puzzle(alice, kind="found", themes=["mateIn2"], date=date(2026, 7, 1)),
        "najdorf": a_puzzle(
            alice, kind="found", eco="B90", opening="Sicilian: Najdorf", date=date(2026, 1, 1)
        ),
    }

    body = next_puzzle(alice_client, query)

    assert body["puzzle"]["id"] == puzzles[expected].pk
    assert body["due"] == 1


def test_filters_by_game(alice_client: Client, alice: User) -> None:
    a_puzzle(alice)
    wanted = a_puzzle(alice)

    page = alice_client.get(f"/api/v1/training/puzzles?game={wanted.game_id}").json()

    assert [p["id"] for p in page["items"]] == [wanted.pk]


def test_a_review_schedules_the_puzzle_and_can_be_rated_again(
    alice_client: Client, alice: User
) -> None:
    puzzle = a_puzzle(alice)

    response = alice_client.post(
        "/api/v1/training/reviews",
        {"card_id": puzzle.card.pk, "correct": True, "elapsed_ms": 3000},
        content_type=AS_JSON,
    )

    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert (body["rating"], body["correct"]) == (ReviewLog.Rating.EASY, True)
    changed = alice_client.patch(
        f"/api/v1/training/reviews/{body['id']}", {"rating": 1}, content_type=AS_JSON
    )
    assert changed.status_code == HTTPStatus.OK
    assert changed.json()["rating"] == ReviewLog.Rating.AGAIN
    assert next_puzzle(alice_client)["due"] == 0  # due again in a few minutes, not now


def test_lists_puzzles_newest_first(alice_client: Client, alice: User) -> None:
    first, second = a_puzzle(alice), a_puzzle(alice)

    page = alice_client.get("/api/v1/training/puzzles").json()

    assert [p["id"] for p in page["items"]] == [second.pk, first.pk]
    assert page["total"] == 2  # noqa: PLR2004


def test_statistics(alice_client: Client, alice: User) -> None:
    due = a_puzzle(alice, due_in=-timedelta(minutes=1))
    a_puzzle(alice, due_in=timedelta(days=5))
    alice_client.post(
        "/api/v1/training/reviews",
        {"card_id": due.card.pk, "correct": False, "elapsed_ms": 9000},
        content_type=AS_JSON,
    )

    body = alice_client.get("/api/v1/training/stats").json()

    assert (body["puzzles"], body["reviewed_today"]) == (2, 1)
    assert body["due_now"] == 0  # the failed one comes back in a few minutes
    assert body["due_today"] == 1
    (week,) = body["weeks"]
    assert (week["reviews"], week["solved"]) == (1, 0)


# Isolation: users only ever see and train their own puzzles.


def test_someone_elses_puzzles_are_not_yours(alice_client: Client, bob: User) -> None:
    bobs = a_puzzle(bob, due_in=-timedelta(days=1))

    assert next_puzzle(alice_client) == {"puzzle": None, "due": 0}
    assert alice_client.get("/api/v1/training/puzzles").json()["total"] == 0
    review = alice_client.post(
        "/api/v1/training/reviews",
        {"card_id": bobs.card.pk, "correct": True, "elapsed_ms": 1000},
        content_type=AS_JSON,
    )
    assert review.status_code == HTTPStatus.NOT_FOUND
    assert alice_client.get("/api/v1/training/stats").json()["puzzles"] == 0


def test_someone_elses_review_cant_be_changed(alice_client: Client, bob: User) -> None:
    log = review(a_puzzle(bob).card, correct=True, elapsed_ms=1000)

    response = alice_client.patch(
        f"/api/v1/training/reviews/{log.pk}", {"rating": 1}, content_type=AS_JSON
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_requires_login(client: Client) -> None:
    assert client.get("/api/v1/training/next").status_code == HTTPStatus.UNAUTHORIZED
