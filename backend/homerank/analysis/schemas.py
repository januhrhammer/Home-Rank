from datetime import datetime

from ninja import Field, Schema

from homerank.analysis.models import AnalysisRun
from homerank.analysis.selectors import EvalWithClass
from homerank.engine.evaluation import MoveClass


class AnalysisRunOut(Schema):
    """An analysis and its progress. The frontend polls it while it is queued or running."""

    id: int
    game_id: int
    status: AnalysisRun.Status
    depth: int
    positions_total: int  # progress: positions_done / positions_total
    positions_done: int
    error: str  # why a failed analysis stopped
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AnalysisRequest(Schema):
    """Games to analyse: some by id, or a whole collection."""

    game_ids: list[int] = Field(default_factory=list, max_length=1000)
    collection: int | None = None
    depth: int | None = Field(None, ge=1, description="Default: the server's ANALYSIS_DEPTH")


class PositionEvalOut(Schema):
    """The engine's view of a position, from White's point of view."""

    ply: int
    depth: int
    score_cp: int | None
    score_mate: int | None  # > 0: White mates; 0: the side to move is checkmated
    win_percent: float  # White's winning chances, 0 to 100
    best_move_uci: str
    pv: list[str]
    move_class: MoveClass | None  # of the move that led to this position

    @staticmethod
    def resolve_ply(item: EvalWithClass) -> int:
        return item.eval.ply

    @staticmethod
    def resolve_depth(item: EvalWithClass) -> int:
        return item.eval.depth

    @staticmethod
    def resolve_score_cp(item: EvalWithClass) -> int | None:
        return item.eval.score_cp

    @staticmethod
    def resolve_score_mate(item: EvalWithClass) -> int | None:
        return item.eval.score_mate

    @staticmethod
    def resolve_win_percent(item: EvalWithClass) -> float:
        return round(item.eval.win_percent, 2)

    @staticmethod
    def resolve_best_move_uci(item: EvalWithClass) -> str:
        return item.eval.best_move_uci

    @staticmethod
    def resolve_pv(item: EvalWithClass) -> list[str]:
        return item.eval.pv


class MistakesOut(Schema):
    inaccuracies: int
    mistakes: int
    blunders: int


class AnalysisSummaryOut(Schema):
    accuracy_white: float | None
    accuracy_black: float | None
    depth: int  # the shallowest search of any position
    engine: str
    analysed_at: datetime


class GameAnalysisOut(Schema):
    """A game's analysis: the latest job, the summary, and every position."""

    run: AnalysisRunOut | None
    summary: AnalysisSummaryOut | None
    positions: list[PositionEvalOut]
    white: MistakesOut  # counted with your thresholds
    black: MistakesOut


class AnalysisSettingsOut(Schema):
    auto_analyse: bool
    inaccuracy: float
    mistake: float
    blunder: float


class AnalysisSettingsPatch(Schema):
    """The settings to change; those left out stay as they are."""

    auto_analyse: bool | None = None
    inaccuracy: float | None = Field(None, gt=0, le=100)
    mistake: float | None = Field(None, gt=0, le=100)
    blunder: float | None = Field(None, gt=0, le=100)
