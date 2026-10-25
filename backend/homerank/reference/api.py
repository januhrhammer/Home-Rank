from http import HTTPStatus
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest
from ninja import Query, Router, Status
from ninja.pagination import paginate

from homerank.accounts.auth import AuthenticatedRequest
from homerank.core.pagination import LimitOffset
from homerank.games import selectors as game_selectors
from homerank.games.models import Collection
from homerank.reference import selectors, services
from homerank.reference.models import ReferenceDatabase, ReferenceGame
from homerank.reference.schemas import (
    CopyIn,
    CopyOut,
    ReferenceDatabaseOut,
    ReferenceGameFilters,
    ReferenceGameItem,
    ReferenceGameOut,
)

router = Router(tags=["reference"])


@router.get("/databases", response=list[ReferenceDatabaseOut])
def list_databases(request: AuthenticatedRequest) -> QuerySet[ReferenceDatabase]:
    """The reference databases, shared by all users; an admin imports them."""
    return selectors.databases()


class GamesPage(LimitOffset):
    """Pages of a database's games. Without filters, the total is the number of games the import
    stored: counting millions of them again for every page took seconds."""

    def paginate_queryset(
        self,
        queryset: QuerySet[Any],
        pagination: LimitOffset.Input,
        request: HttpRequest,
        **params: Any,
    ) -> dict[str, Any]:
        filters: ReferenceGameFilters | None = params.get("filters")
        unfiltered = filters is not None and not any(filters.dict().values())
        database = selectors.database(database_id=params["database_id"])
        if not unfiltered or database.status != ReferenceDatabase.Status.READY:
            return super().paginate_queryset(queryset, pagination, request, **params)
        start = pagination.offset
        return {"items": queryset[start : start + pagination.limit], "total": database.game_count}


@router.get("/databases/{int:database_id}/games", response=list[ReferenceGameItem])
@paginate(GamesPage)
def list_games(
    request: AuthenticatedRequest, database_id: int, filters: Query[ReferenceGameFilters]
) -> QuerySet[ReferenceGame]:
    """A database's games, filtered, newest first."""
    database = selectors.database(database_id=database_id)
    return selectors.games(database=database, filters=filters)


@router.get("/databases/{int:database_id}/games/{int:game_id}", response=ReferenceGameOut)
def get_game(request: AuthenticatedRequest, database_id: int, game_id: int) -> dict[str, object]:
    """One game, with its PGN."""
    game = selectors.game(database=selectors.database(database_id=database_id), game_id=game_id)
    return {**ReferenceGameItem.from_orm(game).dict(), "pgn": selectors.pgn_of(game)}


@router.post(
    "/databases/{int:database_id}/games/{int:game_id}/copy",
    response={HTTPStatus.CREATED: CopyOut, HTTPStatus.OK: CopyOut},
)
def copy_game(
    request: AuthenticatedRequest, database_id: int, game_id: int, data: CopyIn
) -> Status[dict[str, object]]:
    """Copy a game into your games (201), or find the copy you have (200); optionally add it to
    one of your collections (404 if it isn't yours)."""
    game = selectors.game(database=selectors.database(database_id=database_id), game_id=game_id)
    collection = (
        game_selectors.group(Collection, user=request.user, group_id=data.collection)
        if data.collection is not None
        else None
    )
    copy, created = services.copy_game(user=request.user, game=game, collection=collection)
    status = HTTPStatus.CREATED if created else HTTPStatus.OK
    return Status(status, {"game_id": copy.pk, "created": created})
