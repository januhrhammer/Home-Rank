from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction

from homerank.accounts.models import User
from homerank.analysis.models import AnalysisRun, AnalysisSettings, GameAnalysis, PositionEval
from homerank.games.models import Game

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


def make_game(user: User) -> Game:
    return Game.objects.create(
        user=user,
        source=Game.Source.PGN,
        pgn="1. e4 e5 *\n",
        result="*",
        date_pgn="????.??.??",
        time_class="unknown",
        ply_count=2,
        dedup_hash="a" * 64,
    )


def evaluation(game: Game, ply: int, **fields: Any) -> PositionEval:
    values = {
        "depth": 18,
        "score_cp": 20,
        "win_percent": 51.8,
        "engine": "Stockfish 19",
        "analysed_at": datetime(2026, 10, 23, tzinfo=UTC),
        **fields,
    }
    return PositionEval.objects.create(game=game, ply=ply, **values)


def test_a_position_is_evaluated_once_per_game(alice: User) -> None:
    game = make_game(alice)
    evaluation(game, 0, pv=["e2e4", "e7e5"])

    with pytest.raises(IntegrityError), transaction.atomic():
        evaluation(game, 0)
    assert PositionEval.objects.get().pv == ["e2e4", "e7e5"]


def test_deleting_a_game_deletes_its_analysis(alice: User) -> None:
    game = make_game(alice)
    evaluation(game, 0)
    AnalysisRun.objects.create(user=alice, game=game, depth=18)
    GameAnalysis.objects.create(
        game=game, depth=18, engine="Stockfish 19", analysed_at=datetime.now(tz=UTC)
    )

    game.delete()

    assert not PositionEval.objects.exists()
    assert not AnalysisRun.objects.exists()
    assert not GameAnalysis.objects.exists()


def test_settings_have_lichess_like_defaults(alice: User) -> None:
    settings = AnalysisSettings.objects.create(user=alice)

    assert settings.auto_analyse is True
    assert settings.thresholds == (10, 20, 30)


@pytest.mark.parametrize(
    "thresholds",
    [(0, 20, 30), (20, 10, 30), (10, 30, 30), (10, 20, 101)],
)
def test_thresholds_must_rise_and_stay_within_100(
    alice: User, thresholds: tuple[float, float, float]
) -> None:
    inaccuracy, mistake, blunder = thresholds

    with pytest.raises(IntegrityError), transaction.atomic():
        AnalysisSettings.objects.create(
            user=alice, inaccuracy=inaccuracy, mistake=mistake, blunder=blunder
        )


def test_runs_have_no_index_of_their_own_on_game_or_user() -> None:
    # The two composite indexes serve those lookups; more would only slow down writes.
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, AnalysisRun._meta.db_table)
    indexes = sorted(
        c["columns"] for c in constraints.values() if c["index"] and not c["primary_key"]
    )

    assert indexes == [["game_id", "created_at"], ["user_id", "status"]]
