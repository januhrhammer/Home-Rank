from typing import Any

from ninja import Query, Router

from homerank.accounts.auth import AuthenticatedRequest
from homerank.core.errors import DomainError
from homerank.explorer import selectors
from homerank.explorer.schemas import (
    ExplorerOut,
    MyGamesQuery,
    MySearchOut,
    PageQuery,
    ReferenceQuery,
    ReferenceSearchOut,
)
from homerank.explorer.selectors import Explorer, InvalidFenError, MyGameFilters, ReferenceFilters
from homerank.reference import selectors as reference_selectors

router = Router(tags=["explorer"])


class BadPositionError(DomainError):
    detail = "That isn't a valid position (FEN)."


def _my_filters(query: MyGamesQuery) -> MyGameFilters:
    return MyGameFilters(
        color=query.color,
        time_class=query.time_class,
        source=query.source,
        date_from=query.date_from,
        date_to=query.date_to,
    )


def _reference_filters(query: ReferenceQuery) -> ReferenceFilters:
    return ReferenceFilters(
        min_rating=query.min_rating,
        max_rating=query.max_rating,
        date_from=query.date_from,
        date_to=query.date_to,
    )


@router.get("/my", response=ExplorerOut)
def my_explorer(request: AuthenticatedRequest, query: Query[MyGamesQuery]) -> Explorer:
    """The moves you played from the position, with their results."""
    try:
        found = selectors.my_explorer(user=request.user, fen=query.fen, filters=_my_filters(query))
        return selectors.named(found, query.fen)
    except InvalidFenError as error:
        raise BadPositionError from error


@router.get("/reference/{int:database_id}", response=ExplorerOut)
def reference_explorer(
    request: AuthenticatedRequest, database_id: int, query: Query[ReferenceQuery]
) -> Explorer:
    """The moves played from the position in a reference database, with their results."""
    database = reference_selectors.database(database_id=database_id)
    try:
        found = selectors.reference_explorer(
            database=database, fen=query.fen, filters=_reference_filters(query)
        )
        return selectors.named(found, query.fen)
    except InvalidFenError as error:
        raise BadPositionError from error


@router.get("/search/my", response=MySearchOut)
def search_my_games(
    request: AuthenticatedRequest, query: Query[MyGamesQuery], page: Query[PageQuery]
) -> dict[str, Any]:
    """Your games reaching the position, newest first, 50 a page."""
    try:
        found, total = selectors.search_my_games(
            user=request.user, fen=query.fen, filters=_my_filters(query), page=page.page
        )
    except InvalidFenError as error:
        raise BadPositionError from error
    return {"items": [_with_ply(game, ply) for game, ply in found], "total": total}


@router.get("/search/reference/{int:database_id}", response=ReferenceSearchOut)
def search_reference(
    request: AuthenticatedRequest,
    database_id: int,
    query: Query[ReferenceQuery],
    page: Query[PageQuery],
) -> dict[str, Any]:
    """A reference database's games reaching the position, newest first, 50 a page."""
    database = reference_selectors.database(database_id=database_id)
    try:
        found, total, too_common = selectors.search_reference(
            database=database, fen=query.fen, filters=_reference_filters(query), page=page.page
        )
    except InvalidFenError as error:
        raise BadPositionError from error
    items = [_with_ply(game, ply) for game, ply in found]
    return {"items": items, "total": total, "too_common": too_common}


def _with_ply[T](game: T, ply: int) -> T:
    """The game with the ply it reached the position at, for the response's "ply"."""
    game.ply = ply  # type: ignore[attr-defined]
    return game
