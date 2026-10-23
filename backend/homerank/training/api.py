from http import HTTPStatus

from django.db.models import QuerySet
from ninja import Query, Router, Status
from ninja.pagination import paginate

from homerank.accounts.auth import AuthenticatedRequest
from homerank.core.pagination import LimitOffset
from homerank.training import selectors, services
from homerank.training.models import Puzzle, ReviewLog
from homerank.training.schemas import (
    NextPuzzleOut,
    PuzzleFilters,
    PuzzleOut,
    RatingIn,
    ReviewIn,
    ReviewOut,
    TrainingStatsOut,
)
from homerank.training.selectors import TrainingStats

router = Router(tags=["training"])


@router.get("/next", response=NextPuzzleOut)
def next_puzzle(
    request: AuthenticatedRequest, filters: Query[PuzzleFilters]
) -> dict[str, Puzzle | int | None]:
    """The puzzle due longest, with these filters, and how many are due now."""
    puzzle, due = selectors.next_due(user=request.user, filters=filters)
    return {"puzzle": puzzle, "due": due}


@router.post("/reviews", response={HTTPStatus.CREATED: ReviewOut})
def review(request: AuthenticatedRequest, data: ReviewIn) -> Status[ReviewLog]:
    """Record a solve: the rating follows from it (wrong move: Again; solved: by the time per
    move) and the puzzle is scheduled again. Change the rating with PATCH if you disagree."""
    card = selectors.card(user=request.user, card_id=data.card_id)
    log = services.review(card, correct=data.correct, elapsed_ms=data.elapsed_ms)
    return Status(HTTPStatus.CREATED, log)


@router.patch("/reviews/{int:review_id}", response=ReviewOut)
def change_rating(request: AuthenticatedRequest, review_id: int, data: RatingIn) -> ReviewLog:
    """Change the rating of a puzzle's latest review; 409 for an earlier one."""
    log = selectors.review_log(user=request.user, log_id=review_id)
    return services.change_rating(log, rating=data.rating)


@router.get("/puzzles", response=list[PuzzleOut])
@paginate(LimitOffset)
def list_puzzles(request: AuthenticatedRequest, filters: Query[PuzzleFilters]) -> QuerySet[Puzzle]:
    """Your puzzles, newest first."""
    return selectors.puzzles(user=request.user, filters=filters)


@router.get("/stats", response=TrainingStatsOut)
def training_stats(request: AuthenticatedRequest) -> TrainingStats:
    """How many puzzles you have and are due, and how you did in recent weeks."""
    return selectors.stats(user=request.user)
