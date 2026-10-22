"""Reading a user's games data. Every query here is limited to the given user."""

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from homerank.accounts.models import User
from homerank.games.models import ImportRun


def import_runs(*, user: User) -> QuerySet[ImportRun]:
    """The user's imports, the newest first."""
    return ImportRun.objects.filter(user=user).order_by("-created_at", "-id")


def import_run(*, user: User, import_run_id: int) -> ImportRun:
    """One of the user's imports; 404 for anyone else's, so its existence isn't revealed."""
    return get_object_or_404(import_runs(user=user), pk=import_run_id)
