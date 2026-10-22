"""Reading a user's games data. Every query here is limited to the given user."""

from collections.abc import Iterator

from django.db.models import F, Q, QuerySet
from django.db.models.expressions import OrderBy
from django.shortcuts import get_object_or_404

from homerank.accounts.models import User
from homerank.games.models import Game, ImportRun
from homerank.games.schemas import GameFilters

# Filters that compare one field with the given value: the filter's name, and the lookup.
_FIELD_FILTERS = {
    "color": "user_color",
    "result": "result",
    "date_from": "date__gte",
    "date_to": "date__lte",
    "opening": "opening__icontains",
    "source": "source",
    "time_class": "time_class",
    "tag": "tags__id",
    "collection": "collections__id",
    "import_run": "import_run_id",
}

# The result from the user's side; games the user didn't play match none of these.
_OUTCOMES = {
    "win": Q(user_color="white", result="1-0") | Q(user_color="black", result="0-1"),
    "loss": Q(user_color="white", result="0-1") | Q(user_color="black", result="1-0"),
    "draw": ~Q(user_color="") & Q(result="1/2-1/2"),
}


def games(*, user: User, filters: GameFilters) -> QuerySet[Game]:
    """The user's games that match the filters, sorted as they ask, without the PGN text."""
    queryset = Game.objects.filter(user=user).defer("pgn")
    for name, lookup in _FIELD_FILTERS.items():
        value = getattr(filters, name)
        if value is not None:
            queryset = queryset.filter(**{lookup: value})
    if filters.player:
        queryset = queryset.filter(
            Q(white__icontains=filters.player) | Q(black__icontains=filters.player)
        )
    if filters.outcome:
        queryset = queryset.filter(_OUTCOMES[filters.outcome])
    if filters.eco:
        queryset = queryset.filter(eco__startswith=filters.eco.upper())
    if filters.ids is not None:
        queryset = queryset.filter(pk__in=filters.ids)
    return queryset.order_by(*_ordering(filters.sort))


def game(*, user: User, game_id: int) -> Game:
    """One of the user's games; 404 for anyone else's, so its existence isn't revealed."""
    return get_object_or_404(Game.objects.filter(user=user), pk=game_id)


def export_pgn(*, user: User, filters: GameFilters) -> Iterator[str]:
    """The PGN texts of the games the list would show, in its order, as one PGN file.

    The games are read from the database in chunks while the file is sent, so exporting many
    thousands of them never holds them all in memory. Stored texts end with a newline; a blank
    line separates the games.
    """
    texts = games(user=user, filters=filters).values_list("pgn", flat=True)
    for index, pgn in enumerate(texts.iterator(chunk_size=500)):
        yield pgn if index == 0 else "\n" + pgn


def _ordering(sort: str) -> tuple[OrderBy, OrderBy]:
    """Sort by the field, then by id so that pages never overlap; empty values come last."""
    field = sort.removeprefix("-")
    if sort.startswith("-"):
        return F(field).desc(nulls_last=True), F("id").desc()
    return F(field).asc(nulls_last=True), F("id").asc()


def import_runs(*, user: User) -> QuerySet[ImportRun]:
    """The user's imports, the newest first."""
    return ImportRun.objects.filter(user=user).order_by("-created_at", "-id")


def import_run(*, user: User, import_run_id: int) -> ImportRun:
    """One of the user's imports; 404 for anyone else's, so its existence isn't revealed."""
    return get_object_or_404(import_runs(user=user), pk=import_run_id)
