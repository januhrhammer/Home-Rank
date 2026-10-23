from http import HTTPStatus

from ninja import Router, Status

from homerank.accounts.auth import AuthenticatedRequest
from homerank.analysis import selectors, services
from homerank.analysis.models import AnalysisRun, AnalysisSettings
from homerank.analysis.schemas import (
    AnalysisRequest,
    AnalysisRunOut,
    AnalysisSettingsOut,
    AnalysisSettingsPatch,
    GameAnalysisOut,
)
from homerank.analysis.selectors import GameAnalysisView
from homerank.games import selectors as game_selectors
from homerank.games.models import Collection

router = Router(tags=["analysis"])


@router.post("", response={HTTPStatus.ACCEPTED: list[AnalysisRunOut]})
def analyse(request: AuthenticatedRequest, data: AnalysisRequest) -> Status[list[AnalysisRun]]:
    """Analyse games, by id or a whole collection; 404 if one of them isn't yours.

    Returns the analyses that will run, newly queued or already waiting. Games analysed at
    least this deep get none. Poll GET /analysis/games/{id} for the progress.
    """
    games = services.games_of(request.user, data.game_ids)
    if data.collection is not None:
        collection = game_selectors.group(Collection, user=request.user, group_id=data.collection)
        games += list(collection.games.all())
    runs = services.start_analysis(user=request.user, games=games, depth=data.depth)
    return Status(HTTPStatus.ACCEPTED, runs)


@router.get("/games/{int:game_id}", response=GameAnalysisOut)
def game_analysis(request: AuthenticatedRequest, game_id: int) -> GameAnalysisView:
    """A game's analysis: every analysed position, the moves classified with your
    thresholds, both players' accuracy and mistakes, and the latest analysis job."""
    return selectors.game_analysis(user=request.user, game_id=game_id)


@router.get("/settings", response=AnalysisSettingsOut)
def get_settings(request: AuthenticatedRequest) -> AnalysisSettings:
    return selectors.settings_of(request.user)


@router.patch("/settings", response=AnalysisSettingsOut)
def update_settings(
    request: AuthenticatedRequest, changes: AnalysisSettingsPatch
) -> AnalysisSettings:
    """Turn automatic analysis on or off, or change the thresholds (in percentage points of
    winning chances a move loses); 422 unless inaccuracy < mistake < blunder."""
    return services.update_settings(user=request.user, **changes.dict(exclude_none=True))
