"""Reading a user's linked accounts. Every query is filtered by the user."""

from django.db.models import Prefetch, QuerySet
from django.shortcuts import get_object_or_404

from homerank.accounts.models import User
from homerank.sync.models import LinkedAccount, SyncRun


def accounts(*, user: User) -> QuerySet[LinkedAccount]:
    """The user's linked accounts by platform and name, each with its newest sync."""
    newest_run = Prefetch(
        "runs", queryset=SyncRun.objects.order_by("-created_at", "-pk")[:1], to_attr="latest_runs"
    )
    return (
        LinkedAccount.objects.filter(user=user)
        .prefetch_related(newest_run)
        .order_by("platform", "username", "pk")
    )


def account(*, user: User, account_id: int) -> LinkedAccount:
    """One of the user's linked accounts; 404 for anyone else's."""
    return get_object_or_404(accounts(user=user), pk=account_id)
