"""Training with puzzles from a user's own games, scheduled by spaced repetition (FSRS).

Every row belongs to one user, directly or through its card. Queries go through the app's
selectors and services, which always filter by user. See ADR 0014.
"""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from homerank.engine.tactics import PuzzleKind
from homerank.games.models import Game


class Puzzle(models.Model):
    """A position from one of the user's games where one move clearly wins."""

    # The (user, created_at) index below also serves lookups by user.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False)
    # The unique (game, ply) index below also serves lookups by game.
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="puzzles", db_index=False)
    ply = models.PositiveSmallIntegerField()  # the position in the game, as in GamePosition
    kind = models.CharField(max_length=20, choices=[(k.value, k.value) for k in PuzzleKind])
    fen = models.CharField(max_length=100)  # the position, with the solver to move
    # The opponent's move that led to the position, to show it; "" at the game's start.
    last_move_uci = models.CharField(max_length=5, blank=True)
    # The solver's moves and the opponent's replies, in UCI, starting and ending with the solver.
    solution = ArrayField(models.CharField(max_length=5))
    themes = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    # How many percentage points of winning chances were at stake: the user's loss when they
    # missed it, or the opponent's gift.
    win_swing = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (models.UniqueConstraint(fields=["game", "ply"], name="puzzle_unique_ply"),)
        indexes = (models.Index("user", models.F("created_at").desc(), name="puzzle_user_created"),)

    def __str__(self) -> str:
        return f"puzzle from game {self.game_id}, ply {self.ply}"


class PuzzleScan(models.Model):
    """Marks a game as searched for puzzles, so it isn't searched again."""

    game = models.OneToOneField(
        Game, on_delete=models.CASCADE, primary_key=True, related_name="puzzle_scan"
    )
    puzzles_found = models.PositiveSmallIntegerField()
    scanned_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"game {self.game_id}: {self.puzzles_found} puzzles"


class ReviewCard(models.Model):
    """Something the user trains, with its spaced-repetition state. For now always a puzzle;
    repertoire moves follow in a later milestone."""

    class CardType(models.TextChoices):
        PUZZLE = "puzzle"

    # The (user, due_at) index below also serves lookups by user.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False)
    card_type = models.CharField(max_length=10, choices=CardType, default=CardType.PUZZLE)
    puzzle = models.OneToOneField(
        Puzzle, on_delete=models.CASCADE, null=True, blank=True, related_name="card"
    )
    # The fsrs package's Card, as its to_dict() gives it.
    fsrs_state = models.JSONField()
    due_at = models.DateTimeField()  # copied from fsrs_state, for queries

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=~models.Q(card_type="puzzle") | models.Q(puzzle__isnull=False),
                name="review_card_puzzle_set",
            ),
        )
        indexes = (models.Index(fields=["user", "due_at"], name="review_card_user_due"),)

    def __str__(self) -> str:
        return f"{self.card_type} card due {self.due_at:%Y-%m-%d %H:%M}"


class ReviewLog(models.Model):
    """One review of a card: how the user did."""

    class Rating(models.IntegerChoices):  # FSRS's ratings
        AGAIN = 1
        HARD = 2
        GOOD = 3
        EASY = 4

    card = models.ForeignKey(ReviewCard, on_delete=models.CASCADE, related_name="logs")
    rating = models.PositiveSmallIntegerField(choices=Rating)
    correct = models.BooleanField()  # whether the user solved it without a wrong move
    elapsed_ms = models.PositiveIntegerField()  # how long the user took
    # The card's FSRS state before this review, so that the user can still change the rating:
    # the card is then scheduled again from this state.
    card_state_before = models.JSONField()
    reviewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"review of card {self.card_id}: {self.get_rating_display()}"
