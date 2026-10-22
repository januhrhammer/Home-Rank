"""A user's accounts on Lichess and Chess.com, whose games are imported regularly.

Every row belongs to one user. Queries go through the app's selectors and services, which
always filter by user; the models only describe the data and its constraints.
"""

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class LinkedAccount(models.Model):
    """An account on a chess site; its public games are synced into the user's games."""

    class Platform(models.TextChoices):
        LICHESS = "lichess", "Lichess"
        CHESSCOM = "chesscom", "Chess.com"

    # The unique (user, platform, username) index below also serves lookups by user.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False)
    platform = models.CharField(max_length=10, choices=Platform)
    # As the user typed it; the sites themselves ignore the case of usernames.
    username = models.CharField(max_length=50)
    # Disabled accounts are skipped by the scheduled sync; "sync now" still works.
    enabled = models.BooleanField(default=True)
    # Where the next sync starts: all games played before this are already stored. Lichess:
    # when the newest stored game began; Chess.com: the start of the first month that may
    # still get new games. Empty until the first sync has stored something.
    synced_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                "user", "platform", Lower("username"), name="linked_account_unique_per_user"
            ),
        )

    def __str__(self) -> str:
        return f"{self.get_platform_display()}: {self.username}"


class SyncRun(models.Model):
    """One sync of a linked account, run by a background job."""

    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        DONE = "done"
        FAILED = "failed"  # the sync itself failed, not just some of its games

    # The (account, created_at) index below also serves lookups by account.
    account = models.ForeignKey(
        LinkedAccount, on_delete=models.CASCADE, related_name="runs", db_index=False
    )
    status = models.CharField(max_length=10, choices=Status, default=Status.QUEUED)
    games_imported = models.PositiveIntegerField(default=0)
    games_duplicate = models.PositiveIntegerField(default=0)
    games_failed = models.PositiveIntegerField(default=0)
    # The first problems found, as [{"game": "abcd1234", "reason": "illegal san: ..."}].
    errors = models.JSONField(default=list, blank=True)
    job_id = models.BigIntegerField(null=True, blank=True)  # the Procrastinate job
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = (
            # An account's latest run, for its status and for the scheduler.
            models.Index("account", models.F("created_at").desc(), name="sync_run_account_latest"),
        )

    def __str__(self) -> str:
        return f"{self.account} ({self.status})"
