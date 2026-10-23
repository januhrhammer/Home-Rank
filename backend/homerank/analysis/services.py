"""Analysing a user's games with the engine.

start_analysis queues analyses; run_analysis, which the background job calls, lets Stockfish
look at every position of a game and stores what it found. See ADR 0013.
"""

import io
from collections.abc import Iterable
from http import HTTPStatus

import chess
import chess.engine
import chess.pgn
import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from procrastinate.contrib.django import app

from homerank.accounts.models import User
from homerank.analysis.models import AnalysisRun, AnalysisSettings, GameAnalysis, PositionEval
from homerank.core.errors import DomainError
from homerank.engine.analysis import PositionAnalysis, analyse_game
from homerank.engine.evaluation import game_accuracy
from homerank.engine.uci import open_engine
from homerank.games.models import Game

logger = structlog.get_logger(__name__)

# Positions saved per database write; the progress moves on with each.
SAVE_EVERY = 8
ACTIVE = (AnalysisRun.Status.QUEUED, AnalysisRun.Status.RUNNING)


class DepthTooLargeError(DomainError):
    status = HTTPStatus.UNPROCESSABLE_ENTITY

    def __init__(self) -> None:
        self.detail = f"The depth can be at most {settings.ANALYSIS_MAX_DEPTH}."
        super().__init__(self.detail)


def settings_of(user: User) -> AnalysisSettings:
    """The user's analysis settings; the defaults (unsaved) if they never changed them."""
    found = AnalysisSettings.objects.filter(user=user).first()
    return found or AnalysisSettings(user=user)


def start_analysis(
    *, user: User, games: Iterable[Game], depth: int | None = None
) -> list[AnalysisRun]:
    """Queue an analysis of each game that isn't analysed (or queued) at this depth yet.

    Returns the analyses that will analyse the games, new or already queued; games that
    are analysed deeply enough get none.
    """
    depth = depth or settings.ANALYSIS_DEPTH
    if depth > settings.ANALYSIS_MAX_DEPTH:
        raise DepthTooLargeError
    games = list(games)
    analysed = set(
        GameAnalysis.objects.filter(game__in=games, depth__gte=depth).values_list(
            "game_id", flat=True
        )
    )
    active = {
        run.game_id: run
        for run in AnalysisRun.objects.filter(game__in=games, status__in=ACTIVE, depth__gte=depth)
    }
    runs = []
    for game in games:
        if game.pk in analysed:
            continue
        runs.append(active.get(game.pk) or _queue(user, game, depth))
    return runs


def _queue(user: User, game: Game, depth: int) -> AnalysisRun:
    with transaction.atomic():
        run = AnalysisRun.objects.create(user=user, game=game, depth=depth)
        # The lock is one of ANALYSIS_CONCURRENCY slots, so that many games are analysed at
        # once at most. A game always gets the same slot: two analyses of it never overlap.
        slot = game.pk % settings.ANALYSIS_CONCURRENCY
        task = app.configure_task(
            "homerank.analysis.tasks.analyse_game", lock=f"engine-{slot}", queue="analysis"
        )
        run.job_id = task.defer(analysis_run_id=run.pk)
        run.save(update_fields=["job_id"])
    return run


def run_analysis(*, analysis_run_id: int) -> None:
    """Analyse the run's game. Called by the job, not during a request."""
    run = AnalysisRun.objects.select_related("game").get(pk=analysis_run_id)
    run.status = AnalysisRun.Status.RUNNING
    run.started_at = timezone.now()
    run.positions_total = run.game.ply_count + 1
    run.save(update_fields=["status", "started_at", "positions_total"])
    try:
        _analyse(run)
    except Exception as error:
        # The job's boundary: record why the analysis stopped, then let the worker log it.
        run.status = AnalysisRun.Status.FAILED
        run.error = str(error) or type(error).__name__
        raise
    else:
        run.status = AnalysisRun.Status.DONE
    finally:
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "finished_at", "positions_done"])
        logger.info(
            "Analysis finished",
            analysis_run_id=run.pk,
            game_id=run.game_id,
            status=run.status,
            depth=run.depth,
        )


class UnreadableGameError(Exception):
    def __init__(self) -> None:
        super().__init__("The game's PGN can't be read.")


def _analyse(run: AnalysisRun) -> None:
    game = chess.pgn.read_game(io.StringIO(run.game.pgn))
    if game is None:  # can't happen for imported games, which were read before
        raise UnreadableGameError
    limit = chess.engine.Limit(depth=run.depth)
    with open_engine(
        settings.STOCKFISH_PATH, threads=settings.ENGINE_THREADS, hash_mb=settings.ENGINE_HASH_MB
    ) as engine:
        name = engine.id.get("name", "unknown engine")
        batch: list[PositionAnalysis] = []
        for position in analyse_game(engine, game, limit):
            batch.append(position)
            if len(batch) == SAVE_EVERY:
                _save(run, batch, name)
                batch = []
        _save(run, batch, name)
    _sum_up(run.game, white_first=game.board().turn == chess.WHITE)


def _save(run: AnalysisRun, batch: list[PositionAnalysis], engine_name: str) -> None:
    """Store the positions' results, unless a deeper one is stored already, and the progress."""
    now = timezone.now()
    plies = [position.ply for position in batch]
    stored = dict(
        PositionEval.objects.filter(game=run.game, ply__in=plies).values_list("ply", "depth")
    )
    keep = [p for p in batch if p.depth >= stored.get(p.ply, 0)]
    with transaction.atomic():
        PositionEval.objects.bulk_create(
            [
                PositionEval(
                    game=run.game,
                    ply=p.ply,
                    depth=p.depth,
                    score_cp=p.score_cp,
                    score_mate=p.score_mate,
                    win_percent=p.win_percent,
                    best_move_uci=p.best_move_uci,
                    pv=p.pv,
                    engine=engine_name,
                    analysed_at=now,
                )
                for p in keep
            ],
            update_conflicts=True,
            unique_fields=["game", "ply"],
            update_fields=[
                "depth",
                "score_cp",
                "score_mate",
                "win_percent",
                "best_move_uci",
                "pv",
                "engine",
                "analysed_at",
            ],
        )
        run.positions_done += len(batch)
        run.save(update_fields=["positions_done"])


def _sum_up(game: Game, *, white_first: bool) -> None:
    """Update the game's summary from all its stored positions."""
    evals = list(PositionEval.objects.filter(game=game).order_by("ply"))
    accuracy = game_accuracy([e.win_percent for e in evals], white_first=white_first)
    searched = [e for e in evals if e.depth > 0]  # finished positions need no search
    GameAnalysis.objects.update_or_create(
        game=game,
        defaults={
            "accuracy_white": accuracy[0] if accuracy else None,
            "accuracy_black": accuracy[1] if accuracy else None,
            "depth": min((e.depth for e in searched), default=0),
            "engine": evals[-1].engine if evals else "",
            "analysed_at": timezone.now(),
        },
    )


def games_of(user: User, game_ids: Iterable[int]) -> list[Game]:
    """The user's games among these; others' are left out."""
    return list(Game.objects.filter(user=user, pk__in=list(game_ids)))
