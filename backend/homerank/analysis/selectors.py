"""Reading a user's analyses. Every query is filtered by the user."""

import io
from dataclasses import dataclass, field

import chess
import chess.pgn
from django.shortcuts import get_object_or_404

from homerank.accounts.models import User
from homerank.analysis.models import AnalysisRun, AnalysisSettings, GameAnalysis, PositionEval
from homerank.engine.evaluation import MoveClass, classify
from homerank.games.models import Game


@dataclass
class Mistakes:
    """One player's inaccuracies, mistakes and blunders in a game."""

    inaccuracies: int = 0
    mistakes: int = 0
    blunders: int = 0


@dataclass
class EvalWithClass:
    """A position's evaluation, and how good the move that led to it was."""

    eval: PositionEval
    move_class: MoveClass | None  # None for the starting position, or if a neighbour is missing


@dataclass
class GameAnalysisView:
    """Everything the viewer shows of a game's analysis."""

    game: Game
    run: AnalysisRun | None  # the latest analysis, for its status and progress
    summary: GameAnalysis | None
    positions: list[EvalWithClass] = field(default_factory=list)
    white: Mistakes = field(default_factory=Mistakes)
    black: Mistakes = field(default_factory=Mistakes)


def settings_of(user: User) -> AnalysisSettings:
    """The user's analysis settings; the defaults (unsaved) if they never changed them."""
    found = AnalysisSettings.objects.filter(user=user).first()
    return found or AnalysisSettings(user=user)


def game_analysis(*, user: User, game_id: int) -> GameAnalysisView:
    """The analysis of one of the user's games, with the moves classified by the user's
    thresholds; 404 for anyone else's game."""
    game = get_object_or_404(Game.objects.filter(user=user), pk=game_id)
    view = GameAnalysisView(
        game=game,
        run=game.analysis_runs.order_by("-created_at", "-pk").first(),
        summary=GameAnalysis.objects.filter(game=game).first(),
    )
    thresholds = settings_of(user).thresholds
    white_first = _white_moves_first(game)
    previous: PositionEval | None = None
    for evaluation in PositionEval.objects.filter(game=game).order_by("ply"):
        move_class = None
        if previous is not None and previous.ply == evaluation.ply - 1:
            white_moved = (previous.ply % 2 == 0) == white_first
            move_class = classify(
                previous.win_percent,
                evaluation.win_percent,
                white_moved=white_moved,
                thresholds=thresholds,
            )
            _count(view.white if white_moved else view.black, move_class)
        view.positions.append(EvalWithClass(evaluation, move_class))
        previous = evaluation
    return view


def _white_moves_first(game: Game) -> bool:
    """False for games that start from a position with Black to move (a FEN header)."""
    headers = chess.pgn.read_headers(io.StringIO(game.pgn))
    if headers is None or "FEN" not in headers:
        return True
    try:
        return chess.Board(headers["FEN"]).turn == chess.WHITE
    except ValueError:
        return True


def _count(mistakes: Mistakes, move_class: MoveClass) -> None:
    if move_class == MoveClass.INACCURACY:
        mistakes.inaccuracies += 1
    elif move_class == MoveClass.MISTAKE:
        mistakes.mistakes += 1
    elif move_class == MoveClass.BLUNDER:
        mistakes.blunders += 1
