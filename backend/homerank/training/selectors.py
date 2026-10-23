"""Reading a user's puzzles and training. Every query is filtered by the user."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db.models import Count, Q, QuerySet
from django.db.models.functions import TruncWeek
from django.shortcuts import get_object_or_404
from django.utils import timezone

from homerank.accounts.models import User
from homerank.training.models import Puzzle, ReviewCard, ReviewLog
from homerank.training.schemas import PuzzleFilters

# Weeks of history in the training statistics.
STATS_WEEKS = 12


def puzzles(*, user: User, filters: PuzzleFilters) -> QuerySet[Puzzle]:
    """The user's puzzles, newest first, with their game and card."""
    queryset = Puzzle.objects.filter(user=user).select_related("game", "card")
    if filters.game is not None:
        queryset = queryset.filter(game_id=filters.game)
    if filters.kind is not None:
        queryset = queryset.filter(kind=filters.kind)
    if filters.theme:
        queryset = queryset.filter(themes__contains=[filters.theme])
    if filters.eco:
        queryset = queryset.filter(game__eco__istartswith=filters.eco)
    if filters.opening:
        queryset = queryset.filter(game__opening__icontains=filters.opening)
    if filters.date_from is not None:
        queryset = queryset.filter(game__date__gte=filters.date_from)
    if filters.date_to is not None:
        queryset = queryset.filter(game__date__lte=filters.date_to)
    return queryset.order_by("-created_at", "-pk")


def next_due(*, user: User, filters: PuzzleFilters) -> tuple[Puzzle | None, int]:
    """The puzzle due longest, and how many (with these filters) are due now."""
    due = puzzles(user=user, filters=filters).filter(card__due_at__lte=timezone.now())
    return due.order_by("card__due_at", "pk").first(), due.count()


def card(*, user: User, card_id: int) -> ReviewCard:
    """One of the user's cards; 404 for anyone else's."""
    return get_object_or_404(
        ReviewCard.objects.filter(user=user).select_related("puzzle"), pk=card_id
    )


def review_log(*, user: User, log_id: int) -> ReviewLog:
    """One of the user's reviews; 404 for anyone else's."""
    return get_object_or_404(
        ReviewLog.objects.filter(card__user=user).select_related("card"), pk=log_id
    )


@dataclass
class WeekStats:
    week: date  # the Monday the week starts with
    reviews: int
    solved: int


@dataclass
class TrainingStats:
    puzzles: int
    due_now: int
    due_today: int  # by the end of today, in the server's time zone
    reviewed_today: int
    weeks: list[WeekStats]  # the last STATS_WEEKS weeks with reviews, oldest first


def stats(*, user: User) -> TrainingStats:
    now = timezone.now()
    end_of_today = datetime.combine(
        timezone.localdate(now) + timedelta(days=1), datetime.min.time(), tzinfo=now.tzinfo
    )
    start_of_today = end_of_today - timedelta(days=1)
    # Puzzles only: repertoire cards have their own statistics.
    cards = ReviewCard.objects.filter(user=user, card_type=ReviewCard.CardType.PUZZLE)
    logs = ReviewLog.objects.filter(card__in=cards)
    weeks = (
        logs.filter(reviewed_at__gte=now - timedelta(weeks=STATS_WEEKS))
        .annotate(week=TruncWeek("reviewed_at"))
        .values("week")
        .annotate(reviews=Count("pk"), solved=Count("pk", filter=Q(correct=True)))
        .order_by("week")
    )
    return TrainingStats(
        puzzles=Puzzle.objects.filter(user=user).count(),
        due_now=cards.filter(due_at__lte=now).count(),
        due_today=cards.filter(due_at__lt=end_of_today).count(),
        reviewed_today=logs.filter(reviewed_at__gte=start_of_today).count(),
        weeks=[WeekStats(w["week"].date(), w["reviews"], w["solved"]) for w in weeks],
    )
