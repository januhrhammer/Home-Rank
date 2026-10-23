"""Engine analysis of a user's games: what Stockfish thinks of every position, and the jobs.

Every row belongs to one user, directly or through its game. Queries go through the app's
selectors and services, which always filter by user. See ADR 0013.
"""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from homerank.engine.evaluation import DEFAULT_THRESHOLDS
from homerank.games.models import Game


class AnalysisRun(models.Model):
    """One analysis of a game by the engine, run by a background job."""

    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        DONE = "done"
        FAILED = "failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False)
    # The (game, created_at) index below also serves lookups by game.
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name="analysis_runs", db_index=False
    )
    status = models.CharField(max_length=10, choices=Status, default=Status.QUEUED)
    depth = models.PositiveSmallIntegerField()  # how deep the engine searches each position
    positions_total = models.PositiveSmallIntegerField(default=0)  # for the progress bar
    positions_done = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)  # why a failed analysis stopped
    job_id = models.BigIntegerField(null=True, blank=True)  # the Procrastinate job
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = (
            # A game's latest analysis, for its status.
            models.Index("game", models.F("created_at").desc(), name="analysis_run_game_latest"),
            # How many of a user's analyses wait or run, for the queue's status.
            models.Index(
                "user",
                "status",
                condition=models.Q(status__in=["queued", "running"]),
                name="analysis_run_user_active",
            ),
        )

    def __str__(self) -> str:
        return f"game {self.game_id} at depth {self.depth} ({self.status})"


class PositionEval(models.Model):
    """The engine's view of one position of a game's main line, from White's point of view.

    Ply 0 is the starting position, as in games.GamePosition. Analysing a game again only
    replaces a position's result with a deeper (or equally deep) one.
    """

    pk = models.CompositePrimaryKey("game", "ply")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="evals", db_index=False)
    ply = models.PositiveSmallIntegerField()
    depth = models.PositiveSmallIntegerField()  # 0 for finished positions (mate, stalemate, …)
    score_cp = models.IntegerField(null=True, blank=True)  # None when there is a mate
    # Moves to mate, > 0 if White mates; 0 means the side to move is checkmated.
    score_mate = models.SmallIntegerField(null=True, blank=True)
    win_percent = models.FloatField()  # White's winning chances, 0 to 100 (Lichess's formula)
    best_move_uci = models.CharField(max_length=5, blank=True)
    pv = ArrayField(models.CharField(max_length=5), default=list, blank=True)  # UCI moves
    engine = models.CharField(max_length=50)  # e.g. "Stockfish 19"
    analysed_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"game {self.game_id}, ply {self.ply}"


class GameAnalysis(models.Model):
    """A game's analysis summed up, updated after each analysis of it."""

    game = models.OneToOneField(
        Game, on_delete=models.CASCADE, primary_key=True, related_name="analysis"
    )
    accuracy_white = models.FloatField(null=True, blank=True)  # None for a game without moves
    accuracy_black = models.FloatField(null=True, blank=True)
    depth = models.PositiveSmallIntegerField()  # the shallowest search of any position
    engine = models.CharField(max_length=50)
    analysed_at = models.DateTimeField()

    class Meta:
        verbose_name_plural = "game analyses"

    def __str__(self) -> str:
        return f"game {self.game_id} at depth {self.depth}"


class AnalysisSettings(models.Model):
    """A user's choices for analysis. Users without a row have the defaults."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True
    )
    # Analyse new games in which the user played, as they are imported or synced.
    auto_analyse = models.BooleanField(default=True)
    # How many percentage points of winning chances a move may lose before it counts as an
    # inaccuracy, a mistake or a blunder.
    inaccuracy = models.FloatField(default=DEFAULT_THRESHOLDS[0])
    mistake = models.FloatField(default=DEFAULT_THRESHOLDS[1])
    blunder = models.FloatField(default=DEFAULT_THRESHOLDS[2])

    class Meta:
        verbose_name_plural = "analysis settings"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(inaccuracy__gt=0)
                & models.Q(mistake__gt=models.F("inaccuracy"))
                & models.Q(blunder__gt=models.F("mistake"))
                & models.Q(blunder__lte=100),
                name="analysis_thresholds_in_order",
            ),
        )

    def __str__(self) -> str:
        return f"analysis settings of user {self.user_id}"

    @property
    def thresholds(self) -> tuple[float, float, float]:
        return (self.inaccuracy, self.mistake, self.blunder)
