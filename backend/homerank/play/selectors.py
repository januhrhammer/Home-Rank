"""Reading a user's games against bots. Every query is filtered by the user."""

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from homerank.accounts.models import User
from homerank.play.models import BotGame

LISTED = 100  # games listed at most, newest first


def games(*, user: User) -> QuerySet[BotGame]:
    """The user's latest games against bots, newest first."""
    return BotGame.objects.filter(user=user).order_by("-created_at", "-pk")[:LISTED]


def game(*, user: User, game_id: int) -> BotGame:
    """One of the user's games against bots; 404 for anyone else's."""
    return get_object_or_404(BotGame.objects.filter(user=user), pk=game_id)
