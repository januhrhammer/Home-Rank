"""The opening a reference game shows (ADR 0021): named by the positions its moves reach, from
Lichess's opening list, else by its PGN headers. Replayed from the stored moves when shown."""

from homerank.chesslib.bulk import positions_from_packed
from homerank.chesslib.openings import MAX_PLIES, Opening, opening_of, shown
from homerank.reference.models import ReferenceGame


def shown_opening(game: ReferenceGame) -> Opening:
    """The game's opening as shown. Needs the game's moves: a list loads them with the games."""
    cached: Opening | None = getattr(game, "shown_opening_cache", None)
    if cached is not None:
        return cached
    positions = positions_from_packed(game.start_fen, bytes(game.moves), depth=MAX_PLIES + 1)
    found = opening_of(position.zobrist for position in positions)
    result = shown(found, eco=game.eco, opening=game.opening)
    game.shown_opening_cache = result  # type: ignore[attr-defined]
    return result
