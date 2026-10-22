"""A user's games: the games themselves, their positions, collections, tags and imports.

Every row belongs to one user. Queries go through the app's selectors and services, which
always filter by user; the models only describe the data and its constraints.
"""

from typing import TypeVar

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from homerank.chesslib.headers import RESULTS, TimeClass
from homerank.chesslib.players import Side


class ImportRun(models.Model):
    """One upload of a PGN file, imported by a background job."""

    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        DONE = "done"
        FAILED = "failed"  # the import itself failed, not just some of its games

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=Status, default=Status.QUEUED)
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()  # bytes
    bytes_read = models.BigIntegerField(default=0)  # for the progress bar
    games_imported = models.PositiveIntegerField(default=0)
    games_duplicate = models.PositiveIntegerField(default=0)
    games_failed = models.PositiveIntegerField(default=0)
    # The first problems found, as [{"line": 12, "reason": "illegal san: ..."}], so a file full of
    # broken games doesn't fill the database with error messages.
    errors = models.JSONField(default=list, blank=True)
    job_id = models.BigIntegerField(null=True, blank=True)  # the Procrastinate job
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.file_name} ({self.status})"


class Game(models.Model):
    class Source(models.TextChoices):
        PGN = "pgn", "PGN file"
        LICHESS = "lichess", "Lichess"
        CHESSCOM = "chesscom", "Chess.com"

    # The unique (user, dedup_hash) index below also serves lookups by user.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False)
    source = models.CharField(max_length=10, choices=Source)
    # The platform's id for synced games; empty for games from PGN files.
    source_id = models.CharField(max_length=100, blank=True)
    import_run = models.ForeignKey(ImportRun, on_delete=models.SET_NULL, null=True, blank=True)
    # The game's PGN text exactly as imported.
    pgn = models.TextField()

    # Headers, cleaned up by homerank.chesslib.headers: "" or None when unknown.
    white = models.TextField(blank=True)
    black = models.TextField(blank=True)
    white_elo = models.PositiveSmallIntegerField(null=True, blank=True)
    black_elo = models.PositiveSmallIntegerField(null=True, blank=True)
    result = models.CharField(max_length=7, choices=[(r, r) for r in (*RESULTS, "*")])
    # The earliest day the PGN date can mean, for sorting and filtering; date_pgn keeps the
    # exact precision, e.g. "1960.??.??".
    date = models.DateField(null=True, blank=True)
    date_pgn = models.CharField(max_length=10)
    event = models.TextField(blank=True)
    site = models.TextField(blank=True)
    eco = models.CharField(max_length=3, blank=True)
    opening = models.TextField(blank=True)
    time_control = models.CharField(max_length=50, blank=True)
    time_class = models.CharField(max_length=14, choices=[(t.value, t.value) for t in TimeClass])
    termination = models.TextField(blank=True)

    # The side the user played, by the names in their account; "" if they didn't play.
    user_color = models.CharField(
        max_length=5, choices=[(s.value, s.value) for s in Side], blank=True
    )
    ply_count = models.PositiveSmallIntegerField()
    # Recognises the same game imported twice; see homerank.chesslib.dedup and ADR 0008.
    dedup_hash = models.CharField(max_length=64)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["user", "dedup_hash"], name="game_unique_per_user"),
            models.UniqueConstraint(
                fields=["user", "source", "source_id"],
                condition=~models.Q(source_id=""),
                name="game_unique_source_id_per_user",
            ),
        )
        indexes = (
            # The game list's default order (selectors.games). It also serves date ranges and
            # pages far down the list: measured with 100,000 games, 27 ms became 11 ms.
            models.Index(
                "user",
                models.F("date").desc(nulls_last=True),
                models.F("id").desc(),
                name="game_user_date",
            ),
        )

    def __str__(self) -> str:
        return f"{self.white or '?'} - {self.black or '?'} {self.result}"


class GamePosition(models.Model):
    """One position of a game's main line, and the move played from it.

    A game of n half-moves has n + 1 positions: ply 0 is the starting position, ply n the final
    one, which has no move. See homerank.chesslib.positions.
    """

    pk = models.CompositePrimaryKey("game", "ply")
    # The primary key's index covers lookups by game, and the zobrist index those by user.
    game = models.ForeignKey(Game, on_delete=models.CASCADE, db_index=False)
    # Repeated from the game, so that searching a user's positions needs no join.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False)
    ply = models.PositiveSmallIntegerField()
    # The Polyglot Zobrist hash as PostgreSQL's signed bigint (chesslib.positions.as_bigint).
    zobrist = models.BigIntegerField()
    move_san = models.CharField(max_length=10, blank=True)
    move_uci = models.CharField(max_length=5, blank=True)

    class Meta:
        indexes = (models.Index(fields=["user", "zobrist"], name="position_user_zobrist"),)

    def __str__(self) -> str:
        return f"game {self.game_id}, ply {self.ply}"


class Collection(models.Model):
    # The unique (user, name) index below also serves lookups by user.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    games = models.ManyToManyField(Game, related_name="collections", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            # "Openings" and "openings" are the same collection.
            models.UniqueConstraint("user", Lower("name"), name="collection_name_unique_per_user"),
        )

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    # The unique (user, name) index below also serves lookups by user.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False)
    name = models.CharField(max_length=50)
    games = models.ManyToManyField(Game, related_name="tags", blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint("user", Lower("name"), name="tag_name_unique_per_user"),
        )

    def __str__(self) -> str:
        return self.name


# Collections and tags work alike: a name, unique per user whatever its case, and a set of the
# user's games. Services and selectors that serve both are typed with Group, either of them.
Group = TypeVar("Group", Collection, Tag)
