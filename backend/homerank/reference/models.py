"""Reference databases: large collections of games, imported by an admin and shared read-only
by all users. See ADR 0015.

ReferenceDatabase and its imports are ordinary tables. The data of each database (its games,
explorer aggregates and packed position index) lives in partitions of shared tables, one per
database, created and dropped by homerank.reference.repository with raw SQL. ReferenceGame and
ExplorerMove describe two of those tables for reading through the ORM; Django doesn't manage
them (managed = False).
"""

from django.db import models

from homerank.chesslib.bulk import DEFAULT_DEPTH

# The deepest position index a database may have, in plies: the packed index stores a ply in
# one byte.
MAX_DEPTH = 255


class ReferenceDatabase(models.Model):
    # Named apart from the other models' Status: the API's types are named after the class, and
    # these values differ from the imports' and syncs'.
    class DatabaseStatus(models.TextChoices):
        EMPTY = "empty"  # created, nothing imported yet
        IMPORTING = "importing"
        READY = "ready"
        FAILED = "failed"  # the last import failed; the games imported before it remain

    Status = DatabaseStatus

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    # Positions indexed per game, for position search and the explorer.
    depth = models.PositiveSmallIntegerField(default=DEFAULT_DEPTH)
    status = models.CharField(max_length=10, choices=Status, default=Status.EMPTY)
    game_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    imported_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=models.Q(depth__gte=1, depth__lte=MAX_DEPTH),
                name="reference_database_depth",
            ),
        )

    def __str__(self) -> str:
        return self.name


class ReferenceImport(models.Model):
    """An import of one or more files into a reference database, run by a background job."""

    class ImportStatus(models.TextChoices):
        QUEUED = "queued"
        READING = "reading"  # reading the files' games
        INDEXING = "indexing"  # building the explorer and position index
        DONE = "done"
        FAILED = "failed"

    Status = ImportStatus

    database = models.ForeignKey(
        ReferenceDatabase, on_delete=models.CASCADE, related_name="imports"
    )
    status = models.CharField(max_length=10, choices=Status, default=Status.QUEUED)
    error = models.TextField(blank=True)  # why a failed import stopped
    job_id = models.BigIntegerField(null=True, blank=True)  # the Procrastinate job
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"import into {self.database} ({self.status})"


class ReferenceImportFile(models.Model):
    """One file of an import, with how far reading it got, so an interrupted import resumes."""

    reference_import = models.ForeignKey(
        ReferenceImport, on_delete=models.CASCADE, related_name="files"
    )
    path = models.CharField(max_length=500)  # on the server, under REFERENCE_IMPORT_DIR
    size = models.BigIntegerField()  # bytes on disk, compressed
    # Decompressed bytes read up to the end of the last stored batch: reading resumes here.
    offset = models.BigIntegerField(default=0)
    progress = models.FloatField(default=0)  # 0 to 1, by the compressed file's position
    games_read = models.PositiveIntegerField(default=0)
    games_failed = models.PositiveIntegerField(default=0)
    # The first problems, as [{"offset": 1234, "reason": "illegal san: ..."}].
    errors = models.JSONField(default=list, blank=True)
    done = models.BooleanField(default=False)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["reference_import", "path"], name="reference_import_file_unique"
            ),
        )

    def __str__(self) -> str:
        return self.path


class ReferenceGame(models.Model):
    """A game of a reference database (partitioned by database; see repository)."""

    pk = models.CompositePrimaryKey("database", "id")
    database = models.ForeignKey(
        ReferenceDatabase, on_delete=models.DO_NOTHING, db_column="database_id"
    )
    id = models.IntegerField()  # numbered from 1 within its database
    white = models.TextField()
    black = models.TextField()
    white_elo = models.SmallIntegerField(null=True)
    black_elo = models.SmallIntegerField(null=True)
    result = models.CharField(max_length=7)
    date = models.DateField(null=True)
    date_pgn = models.CharField(max_length=10)
    event = models.TextField()
    site = models.TextField()
    eco = models.CharField(max_length=3)
    opening = models.TextField()
    ply_count = models.SmallIntegerField()
    start_fen = models.TextField()  # "" for the usual starting position
    moves = models.BinaryField()  # packed, two bytes per half-move (chesslib.packed)
    dedup_hash = models.BinaryField()  # the first 16 bytes of chesslib.dedup's hash

    class Meta:
        managed = False
        db_table = "reference_game"

    def __str__(self) -> str:
        return f"{self.white} - {self.black} {self.result}"


class ExplorerMove(models.Model):
    """How a move from a position turned out in a reference database (partitioned by
    database), for positions seen in at least two of its games."""

    pk = models.CompositePrimaryKey("database", "zobrist", "move")
    database = models.ForeignKey(
        ReferenceDatabase, on_delete=models.DO_NOTHING, db_column="database_id"
    )
    zobrist = models.BigIntegerField()
    move = models.SmallIntegerField()  # packed (chesslib.packed)
    white = models.IntegerField()  # games won by White after it
    draws = models.IntegerField()
    black = models.IntegerField()
    rating_sum = models.BigIntegerField()  # of both players, where known
    rating_count = models.IntegerField()
    last_year = models.SmallIntegerField(null=True)

    class Meta:
        managed = False
        db_table = "reference_explorer"

    def __str__(self) -> str:
        return f"{self.move} from {self.zobrist}"
