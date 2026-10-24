"""Opening repertoires: the moves a user has prepared for one colour.

A repertoire is stored as its moves, each keyed by the position it is played from, so a
position reached by different move orders (a transposition) is one position with one set of
moves. Its lines are named sets of those moves, each a path from the starting position. Every
row belongs to one user through its repertoire; queries go through the app's selectors and
services, which always filter by user. See ADRs 0016 and 0020.
"""

from django.conf import settings
from django.db import models

from homerank.chesslib.players import Side


class Repertoire(models.Model):
    # The unique (user, name) index below also serves lookups by user.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=5, choices=[(s.value, s.value) for s in Side])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["user", "name"], name="repertoire_unique_name"),
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.color})"


class RepertoireMove(models.Model):
    """One move of a repertoire, from one position to the next."""

    # The unique (repertoire, from_zobrist, move_uci) index below also serves lookups by
    # repertoire.
    repertoire = models.ForeignKey(
        Repertoire, on_delete=models.CASCADE, related_name="moves", db_index=False
    )
    # The position the move is played from: its Polyglot hash (signed, as in GamePosition)
    # and its FEN, to show it without replaying the moves that lead there.
    from_zobrist = models.BigIntegerField()
    from_fen = models.CharField(max_length=100)
    move_uci = models.CharField(max_length=5)
    move_san = models.CharField(max_length=10)
    to_zobrist = models.BigIntegerField()  # the position the move leads to
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["repertoire", "from_zobrist", "move_uci"],
                name="repertoire_move_unique",
            ),
        )

    def __str__(self) -> str:
        return f"{self.move_san} in {self.from_fen}"


class RepertoireLine(models.Model):
    """A named part of a repertoire, e.g. "Open Ruy" in "Ruy Lopez": the moves that belong to it
    (shared with other lines where they overlap), all reachable from the start through them."""

    # The unique (repertoire, name) index below also serves lookups by repertoire.
    repertoire = models.ForeignKey(
        Repertoire, on_delete=models.CASCADE, related_name="lines", db_index=False
    )
    name = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)  # the lines' order in their repertoire
    moves = models.ManyToManyField(
        RepertoireMove, through="RepertoireLineMove", related_name="lines"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["repertoire", "name"], name="repertoire_line_unique"),
        )

    def __str__(self) -> str:
        return f"{self.name} in {self.repertoire.name}"


class RepertoireLineMove(models.Model):
    """That a move belongs to a line."""

    # The unique (line, move) index below also serves lookups by line.
    line = models.ForeignKey(RepertoireLine, on_delete=models.CASCADE, db_index=False)
    move = models.ForeignKey(RepertoireMove, on_delete=models.CASCADE)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["line", "move"], name="repertoire_line_move_unique"),
        )

    def __str__(self) -> str:
        return f"{self.move} in {self.line}"
