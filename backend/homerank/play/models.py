"""Games against a bot: a position played out against Maia or Stockfish (ADR 0017, spec M8).

They are kept apart from the user's games (games.Game): they add nothing to the game list,
statistics, puzzles or repertoire gaps. One can be moved into the user's games on request,
which creates a Game and links it here. Every row belongs to one user; queries go through the
app's selectors and services, which always filter by user.
"""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.lookups import Exact

from homerank.chesslib.players import Side


class Opponent(models.TextChoices):
    MAIA = "maia"  # plays like a person of the rating (a Lichess rating)
    STOCKFISH = "stockfish"  # Stockfish limited to the rating, on its own engine scale


class BotGameStatus(models.TextChoices):
    PLAYING = "playing"
    FINISHED = "finished"


class Termination(models.TextChoices):
    """How a finished game ended."""

    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    THREEFOLD_REPETITION = "threefold_repetition"
    FIFTY_MOVES = "fifty_moves"
    RESIGNATION = "resignation"
    TIMEOUT = "timeout"


RESULTS = ("1-0", "0-1", "1/2-1/2")


def _length(field: str) -> models.Func:
    """The number of items in an array field: Postgres's cardinality, which is 0 for an empty
    one (array_length, behind Django's __len, gives NULL, which a check lets through)."""
    return models.Func(models.F(field), function="cardinality", output_field=models.IntegerField())


class BotGame(models.Model):
    # Listed newest first per user: the (user, created_at) index below serves that.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False)
    # Where the game started (the standard starting position, or any other), and what it was,
    # e.g. "Sicilian and more, after 1. e4 c5", to list and name the game.
    start_fen = models.CharField(max_length=100)
    start_label = models.CharField(max_length=200, blank=True)
    user_color = models.CharField(max_length=5, choices=[(s.value, s.value) for s in Side])
    opponent = models.CharField(max_length=10, choices=Opponent.choices)
    opponent_elo = models.PositiveSmallIntegerField()

    # The moves from start_fen, in UCI, and how long each one took in milliseconds: the
    # user's thinking time, or the bot's computing time. Always the same length.
    moves = ArrayField(models.CharField(max_length=5), default=list, blank=True)
    move_ms = ArrayField(models.PositiveIntegerField(), default=list, blank=True)

    # The clock: none (untimed) or a base time and an increment per move. Each side's time
    # left follows from these and move_ms; turn_started_at is when the side to move began,
    # so the running clock survives a reload.
    clock_base_ms = models.PositiveIntegerField(null=True, blank=True)
    clock_increment_ms = models.PositiveIntegerField(null=True, blank=True)
    turn_started_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=8, choices=BotGameStatus.choices, default=BotGameStatus.PLAYING
    )
    result = models.CharField(
        max_length=7, choices=[(r, r) for r in RESULTS], blank=True
    )  # empty while playing
    termination = models.CharField(max_length=21, choices=Termination.choices, blank=True)

    # The user's game this one was moved into, if it was.
    saved_game = models.OneToOneField(
        "games.Game", on_delete=models.SET_NULL, null=True, blank=True, related_name="bot_game"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = (models.Index(fields=["user", "-created_at"], name="bot_game_user_created"),)
        constraints = (
            models.CheckConstraint(
                condition=Exact(_length("moves"), _length("move_ms")),
                name="bot_game_moves_have_times",
            ),
            # A clock has both parts, or neither.
            models.CheckConstraint(
                condition=models.Q(clock_base_ms__isnull=True, clock_increment_ms__isnull=True)
                | models.Q(
                    clock_base_ms__isnull=False,  # or base > 0 is NULL, which passes a check
                    clock_base_ms__gt=0,
                    clock_increment_ms__isnull=False,
                ),
                name="bot_game_clock_complete",
            ),
            # A finished game has its result, how it ended and when; a game being played has
            # none of them.
            models.CheckConstraint(
                condition=models.Q(status=BotGameStatus.PLAYING, result="", termination="")
                & models.Q(finished_at__isnull=True)
                | models.Q(status=BotGameStatus.FINISHED, finished_at__isnull=False)
                & ~models.Q(result="")
                & ~models.Q(termination=""),
                name="bot_game_finished_complete",
            ),
        )

    def __str__(self) -> str:
        return f"{self.user_color} vs {self.opponent} {self.opponent_elo} ({self.status})"
