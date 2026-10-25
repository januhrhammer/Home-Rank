"""The opening a game shows (ADR 0021): named by the positions its moves reach, from Lichess's
opening list, else by its PGN headers. Used by the API's schemas, which show it, and the
selectors, which load the positions with the games."""

from django.db.models import Prefetch, QuerySet

from homerank.chesslib.openings import MAX_PLIES, Opening, opening_of, shown
from homerank.games.models import Game, GamePosition


# Quoted: Prefetch is generic only for mypy and can't be subscripted at runtime.
def opening_positions() -> "Prefetch[str, QuerySet[GamePosition], str]":
    """Loads each game's first positions with a list of games, in one query for all of them,
    as `game.opening_positions`."""
    return Prefetch(
        "gameposition_set",
        queryset=GamePosition.objects.filter(ply__lte=MAX_PLIES)
        .only("game", "ply", "zobrist")
        .order_by("ply"),
        to_attr="opening_positions",
    )


def shown_opening(game: Game) -> Opening:
    """The game's opening as shown; its positions from opening_positions() if loaded with it."""
    cached: Opening | None = getattr(game, "shown_opening_cache", None)
    if cached is not None:
        return cached
    positions = getattr(game, "opening_positions", None)
    if positions is None:
        positions = GamePosition.objects.filter(game=game, ply__lte=MAX_PLIES).order_by("ply")
    found = opening_of(position.zobrist for position in positions)
    result = shown(found, eco=game.eco, opening=game.opening)
    game.shown_opening_cache = result  # type: ignore[attr-defined]
    return result
