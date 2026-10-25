"""Reading a user's games data. Every query here is limited to the given user."""

from collections.abc import Iterator

from django.db.models import Count, F, Prefetch, Q, QuerySet
from django.db.models.expressions import OrderBy
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404

from homerank.accounts.models import User
from homerank.games.models import Collection, Game, Group, ImportRun, Tag
from homerank.games.openings import opening_positions
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
    queryset = Game.objects.filter(user=user).defer("pgn").prefetch_related(opening_positions())
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


def game_list(*, user: User, filters: GameFilters) -> QuerySet[Game]:
    """games() with each game's tags, as the game list shows them."""
    return games(user=user, filters=filters).prefetch_related(_by_name("tags", Tag))


def game(*, user: User, game_id: int) -> Game:
    """One of the user's games, with its tags and collections; 404 for anyone else's game."""
    queryset = Game.objects.filter(user=user).prefetch_related(
        _by_name("tags", Tag), _by_name("collections", Collection), opening_positions()
    )
    return get_object_or_404(queryset, pk=game_id)


# Quoted: Prefetch is generic only for mypy and can't be subscripted at runtime.
def _by_name(lookup: str, model: type[Group]) -> "Prefetch[str, QuerySet[Group], str]":
    return Prefetch(lookup, queryset=model.objects.only("id", "name").order_by(Lower("name")))


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


def groups(model: type[Group], *, user: User) -> QuerySet[Group]:
    """The user's collections or tags, by name, each with its number of games (game_count)."""
    return (
        model.objects.filter(user=user)
        .annotate(game_count=Count("games"))
        .order_by(Lower("name"), "id")
    )


def group(model: type[Group], *, user: User, group_id: int) -> Group:
    """One of the user's collections or tags; 404 for anyone else's."""
    return get_object_or_404(groups(model, user=user), pk=group_id)
