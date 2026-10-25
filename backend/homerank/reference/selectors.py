"""Reading reference databases. They are shared: every logged-in user reads all of them."""

from django.db.models import F, Q, QuerySet
from django.shortcuts import get_object_or_404

from homerank.chesslib.packed import to_pgn
from homerank.reference.models import ReferenceDatabase, ReferenceGame
from homerank.reference.schemas import ReferenceGameFilters


def databases() -> QuerySet[ReferenceDatabase]:
    return ReferenceDatabase.objects.order_by("name")


def database(*, database_id: int) -> ReferenceDatabase:
    return get_object_or_404(ReferenceDatabase, pk=database_id)


def games(*, database: ReferenceDatabase, filters: ReferenceGameFilters) -> QuerySet[ReferenceGame]:
    """The database's games, filtered, newest first; with their moves, which name their
    opening (a few dozen bytes each)."""
    queryset = ReferenceGame.objects.filter(database=database).defer("dedup_hash")
    if filters.player:
        queryset = queryset.filter(
            Q(white__icontains=filters.player) | Q(black__icontains=filters.player)
        )
    for lookup, value in (
        ("eco__istartswith", filters.eco),
        ("result", filters.result),
        ("date__gte", filters.date_from),
        ("date__lte", filters.date_to),
        ("white_elo__gte", filters.min_rating),
        ("black_elo__gte", filters.min_rating),
    ):
        if value:
            queryset = queryset.filter(**{lookup: value})
    return queryset.order_by(F("date").desc(nulls_last=True), "-id")


def game(*, database: ReferenceDatabase, game_id: int) -> ReferenceGame:
    return get_object_or_404(ReferenceGame, database=database, id=game_id)


def pgn_of(game: ReferenceGame) -> str:
    """The game as PGN, rebuilt from its headers and packed moves."""
    headers = {
        "Event": game.event or "?",
        "Site": game.site or "?",
        "Date": game.date_pgn,
        "White": game.white or "?",
        "Black": game.black or "?",
        "Result": game.result,
    }
    for name, value in (
        ("WhiteElo", game.white_elo),
        ("BlackElo", game.black_elo),
        ("ECO", game.eco),
        ("Opening", game.opening),
    ):
        if value:
            headers[name] = str(value)
    return to_pgn(headers, bytes(game.moves), game.start_fen)
