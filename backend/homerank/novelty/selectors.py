"""Reading a user's novelty searches. Every query is filtered by the user."""

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from homerank.accounts.models import User
from homerank.novelty.models import NoveltySearch, NoveltyTry


def searches(*, user: User) -> QuerySet[NoveltySearch]:
    """The user's searches, newest first."""
    return NoveltySearch.objects.filter(user=user).order_by("-created_at", "-pk")


def search(*, user: User, search_id: int) -> NoveltySearch:
    """One of the user's searches; 404 for anyone else's."""
    return get_object_or_404(NoveltySearch.objects.filter(user=user), pk=search_id)


def tries(search: NoveltySearch) -> QuerySet[NoveltyTry]:
    """The tries of the search's last finished step, the best first."""
    return search.tries.order_by("rank")
