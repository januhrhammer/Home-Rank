"""Analysing games: queueing analyses, and the job that runs Stockfish over a game."""

import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from procrastinate.contrib.django.models import ProcrastinateJob
from pytest_django import Settings

from homerank.accounts.models import User
from homerank.analysis import services, tasks
from homerank.analysis.models import AnalysisRun, GameAnalysis, PositionEval
from homerank.analysis.services import DepthTooLargeError, run_analysis, start_analysis
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.games.models import Game
from homerank.games.services import GamesNotFoundError, new_game, store_games

pytestmark = pytest.mark.django_db

SCHOLARS_MATE = """\
[White "alice64"]
[Black "bob_b"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0
"""
DEPTH = 8  # quick: these tests are about storing results, not about chess


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice", player_names=["alice64"])


@pytest.fixture
def quick(settings: Settings) -> None:
    settings.ANALYSIS_DEPTH = DEPTH


def a_game(user: User, text: str = SCHOLARS_MATE) -> Game:
    (item,) = read_pgn(io.BytesIO(text.encode()))
    assert isinstance(item, PgnGame)
    store_games(user, [new_game(user, item)])
    return Game.objects.filter(user=user).latest("pk")


def analysed(user: User, game: Game, depth: int = DEPTH) -> AnalysisRun:
    (run,) = start_analysis(user=user, games=[game], depth=depth)
    run_analysis(analysis_run_id=run.pk)
    run.refresh_from_db()
    return run


# ---------------------------------------------------------------- queueing


def test_queues_an_analysis_at_the_default_depth(alice: User, settings: Settings) -> None:
    settings.ANALYSIS_DEPTH = 18
    game = a_game(alice)

    (run,) = start_analysis(user=alice, games=[game])

    assert (run.status, run.depth, run.user, run.game) == ("queued", 18, alice, game)
    job = ProcrastinateJob.objects.get(id=run.job_id)
    assert job.task_name == "homerank.analysis.tasks.analyse_game"
    assert job.queue_name == "analysis"
    assert job.args == {"analysis_run_id": run.pk}


def test_a_game_gets_the_same_engine_slot_each_time(alice: User, settings: Settings) -> None:
    settings.ANALYSIS_CONCURRENCY = 3
    game = a_game(alice)

    first = start_analysis(user=alice, games=[game], depth=10)[0]
    deeper = start_analysis(user=alice, games=[game], depth=20)[0]

    locks = {ProcrastinateJob.objects.get(id=run.job_id).lock for run in (first, deeper)}
    assert locks == {f"engine-{game.pk % 3}"}  # never analysed twice at the same time


def test_a_queued_analysis_deep_enough_isnt_queued_again(alice: User) -> None:
    game = a_game(alice)
    (first,) = start_analysis(user=alice, games=[game], depth=20)

    assert start_analysis(user=alice, games=[game], depth=16) == [first]
    (deeper,) = start_analysis(user=alice, games=[game], depth=24)
    assert deeper != first
    assert AnalysisRun.objects.count() == len([first, deeper])


def test_a_game_analysed_deeply_enough_needs_no_analysis(alice: User) -> None:
    game = a_game(alice)
    GameAnalysis.objects.create(
        game=game, depth=20, engine="Stockfish 19", analysed_at=datetime.now(tz=UTC)
    )

    assert start_analysis(user=alice, games=[game], depth=20) == []
    assert len(start_analysis(user=alice, games=[game], depth=22)) == 1


def test_the_depth_has_a_limit(alice: User, settings: Settings) -> None:
    settings.ANALYSIS_MAX_DEPTH = 30

    with pytest.raises(DepthTooLargeError, match="at most 30"):
        start_analysis(user=alice, games=[a_game(alice)], depth=31)


def test_only_your_own_games_can_be_chosen(alice: User) -> None:
    bob = User.objects.create_user(username="bob")
    mine, bobs = a_game(alice), a_game(bob)

    assert services.games_of(alice, [mine.pk]) == [mine]
    with pytest.raises(GamesNotFoundError):
        services.games_of(alice, [mine.pk, bobs.pk])  # all or nothing


# ---------------------------------------------------------------- the job


@pytest.mark.engine
@pytest.mark.usefixtures("quick")
def test_the_job_analyses_every_position_and_sums_up(alice: User) -> None:
    game = a_game(alice)

    run = analysed(alice, game)

    assert run.status == AnalysisRun.Status.DONE
    assert (run.positions_done, run.positions_total) == (8, 8)
    assert run.started_at is not None
    assert run.finished_at is not None
    evals = list(PositionEval.objects.filter(game=game).order_by("ply"))
    assert [e.ply for e in evals] == list(range(8))
    assert evals[6].best_move_uci == "h5f7"  # mate in one
    assert evals[0].engine.startswith("Stockfish ")
    summary = GameAnalysis.objects.get(game=game)
    assert summary.depth >= DEPTH
    assert summary.accuracy_white is not None
    assert summary.accuracy_black is not None
    assert summary.accuracy_black < summary.accuracy_white  # 3...Nf6?? lost at once


@pytest.mark.engine
@pytest.mark.usefixtures("quick")
def test_a_shallower_analysis_keeps_the_deeper_results(alice: User) -> None:
    game = a_game(alice)
    deep = PositionEval.objects.create(
        game=game,
        ply=0,
        depth=40,
        score_cp=33,
        win_percent=53.0,
        best_move_uci="e2e4",
        engine="Stockfish 19",
        analysed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    analysed(alice, game)

    kept = PositionEval.objects.get(game=game, ply=0)
    assert (kept.depth, kept.score_cp, kept.analysed_at) == (40, 33, deep.analysed_at)
    assert PositionEval.objects.get(game=game, ply=1).depth >= DEPTH


@pytest.mark.usefixtures("quick")
def test_a_missing_engine_fails_the_analysis_with_a_reason(
    alice: User, settings: Settings, tmp_path: Path
) -> None:
    settings.STOCKFISH_PATH = str(tmp_path / "no-stockfish")
    (run,) = start_analysis(user=alice, games=[a_game(alice)])

    with pytest.raises(FileNotFoundError):
        run_analysis(analysis_run_id=run.pk)

    run.refresh_from_db()
    assert run.status == AnalysisRun.Status.FAILED
    assert "no-stockfish" in run.error
    assert run.finished_at is not None


@pytest.mark.engine
@pytest.mark.usefixtures("quick")
def test_the_task_runs_the_analysis(alice: User) -> None:
    (run,) = start_analysis(user=alice, games=[a_game(alice)])

    tasks.analyse_game(analysis_run_id=run.pk)

    run.refresh_from_db()
    assert run.status == AnalysisRun.Status.DONE
