"""The analysis API: starting analyses, reading a game's analysis, and the settings."""

import itertools
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import pytest
from django.test import Client

from homerank.accounts.models import User
from homerank.analysis.models import AnalysisRun, AnalysisSettings, GameAnalysis, PositionEval
from homerank.games.models import Collection, Game

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


def make_game(user: User, pgn: str = "1. e4 e5 2. Qh5 Ke7 *\n") -> Game:
    return Game.objects.create(
        user=user,
        source=Game.Source.PGN,
        pgn=pgn,
        result="*",
        date_pgn="????.??.??",
        time_class="unknown",
        ply_count=4,
        dedup_hash=f"{next(_hashes):064}",
    )


def store_evals(game: Game, wins: list[float]) -> None:
    """Results for the game's positions, with White's winning chances as given."""
    for ply, win in enumerate(wins):
        PositionEval.objects.create(
            game=game,
            ply=ply,
            depth=18,
            score_cp=0,
            win_percent=win,
            best_move_uci="e2e4",
            pv=["e2e4", "e7e5"],
            engine="Stockfish 19",
            analysed_at=datetime(2026, 10, 23, tzinfo=UTC),
        )


def analyse(client: Client, **data: Any) -> Any:
    return client.post("/api/v1/analysis", data, content_type=AS_JSON)


# ---------------------------------------------------------------- starting analyses


def test_queues_analyses_of_games(alice_client: Client, alice: User) -> None:
    games = [make_game(alice), make_game(alice)]

    response = analyse(alice_client, game_ids=[g.pk for g in games], depth=12)

    assert response.status_code == HTTPStatus.ACCEPTED
    runs = response.json()
    assert sorted(r["game_id"] for r in runs) == sorted(g.pk for g in games)
    assert {(r["status"], r["depth"]) for r in runs} == {("queued", 12)}


def test_queues_analyses_of_a_collection(alice_client: Client, alice: User) -> None:
    collection = Collection.objects.create(user=alice, name="Openings")
    game = make_game(alice)
    collection.games.add(game)

    response = analyse(alice_client, collection=collection.pk)

    assert [r["game_id"] for r in response.json()] == [game.pk]


def test_the_depth_has_limits(alice_client: Client, alice: User) -> None:
    game = make_game(alice)

    assert analyse(alice_client, game_ids=[game.pk], depth=0).status_code == (
        HTTPStatus.UNPROCESSABLE_ENTITY
    )
    too_deep = analyse(alice_client, game_ids=[game.pk], depth=99)
    assert too_deep.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "at most 30" in too_deep.json()["detail"]


# ---------------------------------------------------------------- a game's analysis


def test_a_game_without_analysis(alice_client: Client, alice: User) -> None:
    game = make_game(alice)

    body = alice_client.get(f"/api/v1/analysis/games/{game.pk}").json()

    assert (body["run"], body["summary"], body["positions"]) == (None, None, [])


def test_shows_each_position_with_its_move_classified(alice_client: Client, alice: User) -> None:
    game = make_game(alice)
    # 1. e4 (fine) e5 (fine) 2. Qh5 (White loses 12: inaccuracy) Ke7 (Black loses 35: blunder)
    store_evals(game, [55.0, 56.0, 55.0, 43.0, 78.0])
    GameAnalysis.objects.create(
        game=game,
        accuracy_white=81.2,
        accuracy_black=44.5,
        depth=18,
        engine="Stockfish 19",
        analysed_at=datetime(2026, 10, 23, tzinfo=UTC),
    )
    AnalysisRun.objects.create(user=alice, game=game, depth=18, status="done")

    body = alice_client.get(f"/api/v1/analysis/games/{game.pk}").json()

    assert [p["move_class"] for p in body["positions"]] == [
        None,
        "good",
        "good",
        "inaccuracy",
        "blunder",
    ]
    first = body["positions"][0]
    assert (first["ply"], first["win_percent"], first["pv"]) == (0, 55.0, ["e2e4", "e7e5"])
    assert body["white"] == {"inaccuracies": 1, "mistakes": 0, "blunders": 0}
    assert body["black"] == {"inaccuracies": 0, "mistakes": 0, "blunders": 1}
    assert body["summary"]["accuracy_white"] == pytest.approx(81.2)
    assert body["run"]["status"] == "done"


def test_moves_are_classified_with_your_thresholds(alice_client: Client, alice: User) -> None:
    game = make_game(alice)
    store_evals(game, [55.0, 56.0, 55.0, 43.0, 78.0])
    AnalysisSettings.objects.create(user=alice, inaccuracy=5, mistake=10, blunder=40)

    body = alice_client.get(f"/api/v1/analysis/games/{game.pk}").json()

    assert [p["move_class"] for p in body["positions"]][3:] == ["mistake", "mistake"]


def test_a_game_from_a_position_with_black_to_move(alice_client: Client, alice: User) -> None:
    fen = "4k3/8/8/8/8/8/4P3/4K3 b - - 0 1"
    game = make_game(alice, pgn=f'[SetUp "1"]\n[FEN "{fen}"]\n\n1... Kd7 2. e4 *\n')
    store_evals(game, [50.0, 80.0])  # Black's first move loses 30

    body = alice_client.get(f"/api/v1/analysis/games/{game.pk}").json()

    assert body["black"]["blunders"] == 1
    assert body["white"]["blunders"] == 0


# ---------------------------------------------------------------- settings


def test_settings_start_with_the_defaults(alice_client: Client) -> None:
    body = alice_client.get("/api/v1/analysis/settings").json()

    assert body == {"auto_analyse": True, "inaccuracy": 10, "mistake": 20, "blunder": 30}


def test_changes_settings(alice_client: Client, alice: User) -> None:
    response = alice_client.patch(
        "/api/v1/analysis/settings", {"auto_analyse": False, "blunder": 25}, content_type=AS_JSON
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["blunder"] == 25  # noqa: PLR2004
    stored = AnalysisSettings.objects.get(user=alice)
    assert (stored.auto_analyse, stored.thresholds) == (False, (10, 20, 25))


def test_thresholds_must_rise(alice_client: Client) -> None:
    response = alice_client.patch(
        "/api/v1/analysis/settings", {"mistake": 35}, content_type=AS_JSON
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert not AnalysisSettings.objects.exists()


# Isolation: users only ever see and analyse their own games.


def test_someone_elses_game_is_not_found(alice_client: Client, bob: User) -> None:
    bobs = make_game(bob)
    store_evals(bobs, [50.0, 50.0])

    assert alice_client.get(f"/api/v1/analysis/games/{bobs.pk}").status_code == (
        HTTPStatus.NOT_FOUND
    )
    assert analyse(alice_client, game_ids=[bobs.pk]).status_code == HTTPStatus.NOT_FOUND
    assert not AnalysisRun.objects.exists()


def test_someone_elses_collection_is_not_found(alice_client: Client, bob: User) -> None:
    bobs = Collection.objects.create(user=bob, name="Secret")
    bobs.games.add(make_game(bob))

    assert analyse(alice_client, collection=bobs.pk).status_code == HTTPStatus.NOT_FOUND
    assert not AnalysisRun.objects.exists()


def test_settings_are_your_own(alice_client: Client, bob: User) -> None:
    AnalysisSettings.objects.create(user=bob, auto_analyse=False)

    assert alice_client.get("/api/v1/analysis/settings").json()["auto_analyse"] is True


def test_requires_login(client: Client) -> None:
    assert client.get("/api/v1/analysis/settings").status_code == HTTPStatus.UNAUTHORIZED
