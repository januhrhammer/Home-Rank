"""Novelty searches and the tries they found (ADR 0022).

A search runs as a background job for up to its time limit, deepening step by step; after each
step its tries are replaced by the new step's. Every row belongs to one user through its search;
queries go through the app's selectors and services, which always filter by user.
"""

from django.conf import settings
from django.db import models

from homerank.chesslib.players import Side


class RatingKind(models.TextChoices):
    """What kind of rating the user knows the opponent by; Maia takes Lichess ratings."""

    LICHESS = "lichess"
    FIDE = "fide"
    DWZ = "dwz"


class SearchStatus(models.TextChoices):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"  # reached its time limit, or searched every step
    CANCELLED = "cancelled"  # stopped by the user; the tries found so far stay
    FAILED = "failed"


class NoveltySearch(models.Model):
    # The (user, created_at) index below also serves lookups by user.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False)
    start_fen = models.CharField(max_length=100)
    # The moves from the starting position that led there (UCI), if known, to show the line.
    start_moves = models.JSONField(default=list, blank=True)
    start_label = models.CharField(max_length=200, blank=True)
    side = models.CharField(max_length=5, choices=[(s.value, s.value) for s in Side])
    rating = models.PositiveSmallIntegerField()  # the opponent's, as the user entered it
    rating_kind = models.CharField(max_length=7, choices=RatingKind)
    elo = models.PositiveSmallIntegerField()  # the Lichess rating Maia plays at
    budget_cp = models.PositiveSmallIntegerField()
    limit_minutes = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=9, choices=SearchStatus, default=SearchStatus.QUEUED)
    own_moves = models.PositiveSmallIntegerField(default=0)  # of the last finished step
    cancel_requested = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    job_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = (models.Index(fields=["user", "-created_at"], name="novelty_search_user_new"),)

    def __str__(self) -> str:
        return f"novelty search {self.pk} ({self.status})"


class NoveltyTry(models.Model):
    """One try of a search's last finished step. See homerank.engine.novelty.Try."""

    # The (search, rank) index below also serves lookups by search.
    search = models.ForeignKey(
        NoveltySearch, on_delete=models.CASCADE, related_name="tries", db_index=False
    )
    rank = models.PositiveSmallIntegerField()  # 0 is the best
    line = models.JSONField()  # moves (UCI) from the search's start to the try's position
    uci = models.CharField(max_length=5)
    san = models.CharField(max_length=10)
    cp = models.SmallIntegerField()  # for the user, checked at depth 24
    practical = models.FloatField()  # expected score against the opponent, 0 to 1
    best_san = models.CharField(max_length=10)  # the engine's move there instead
    best_practical = models.FloatField()
    reach = models.FloatField()  # how often the opponent's likely moves lead there
    # [{"san", "uci", "found"}]: the opponent's moves along the refutation, and how likely each
    # (or one nearly as good) is found.
    refutation = models.JSONField()
    # Games in the first reference database reaching the position after the try; null without
    # a reference database.
    reference_games = models.IntegerField(null=True, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["search", "rank"], name="novelty_try_unique_rank"),
        )

    def __str__(self) -> str:
        return f"{self.san} in search {self.search_id}"
