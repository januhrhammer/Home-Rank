"""Reading a user's repertoires. Every query is filtered by the user."""

from django.db.models import Count, QuerySet
from django.shortcuts import get_object_or_404

from homerank.accounts.models import User
from homerank.repertoire.models import Repertoire, RepertoireMove


def repertoires(*, user: User) -> QuerySet[Repertoire]:
    """The user's repertoires by name, each with its number of moves."""
    return (
        Repertoire.objects.filter(user=user)
        .annotate(move_count=Count("moves"))
        .order_by("name", "pk")
    )


def repertoire(*, user: User, repertoire_id: int) -> Repertoire:
    """One of the user's repertoires; 404 for anyone else's."""
    return get_object_or_404(Repertoire.objects.filter(user=user), pk=repertoire_id)


def moves(repertoire: Repertoire) -> QuerySet[RepertoireMove]:
    """All of the repertoire's moves, in the order they were added."""
    return repertoire.moves.order_by("pk")


def move(*, user: User, repertoire_id: int, move_id: int) -> RepertoireMove:
    """One move of one of the user's repertoires; 404 for anyone else's."""
    return get_object_or_404(
        RepertoireMove.objects.filter(
            repertoire__user=user, repertoire_id=repertoire_id
        ).select_related("repertoire"),
        pk=move_id,
    )
