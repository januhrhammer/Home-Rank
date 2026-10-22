from http import HTTPStatus

from django.db.models import QuerySet
from django.http import HttpResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header
from ninja import File, Query, Router, Status, UploadedFile
from ninja.pagination import paginate

from homerank.accounts.auth import AuthenticatedRequest
from homerank.core.pagination import LimitOffset
from homerank.games import selectors, services
from homerank.games.models import Collection, Game, ImportRun, Tag
from homerank.games.schemas import (
    CollectionIn,
    CollectionOut,
    CollectionPatch,
    GameFilters,
    GameIdsIn,
    GameListItem,
    GameOut,
    ImportOut,
    TagIn,
    TagOut,
)

router = Router(tags=["games"])
collections_router = Router(tags=["collections"])
tags_router = Router(tags=["tags"])


@router.get("", response=list[GameListItem])
@paginate(LimitOffset)
def list_games(request: AuthenticatedRequest, filters: Query[GameFilters]) -> QuerySet[Game]:
    """Your games, filtered and sorted; the newest first unless sorted otherwise."""
    return selectors.game_list(user=request.user, filters=filters)


# The media type registered for PGN.
PGN_CONTENT_TYPE = "application/vnd.chess-pgn; charset=utf-8"


@router.get("/export")
def export_games(
    request: AuthenticatedRequest, filters: Query[GameFilters]
) -> StreamingHttpResponse:
    """Download the games the list would show, with the same filters, as one PGN file.

    For example ?collection=3 for a collection, or ?ids=1&ids=5 for a selection.
    """
    return StreamingHttpResponse(
        selectors.export_pgn(user=request.user, filters=filters),
        content_type=PGN_CONTENT_TYPE,
        headers={"Content-Disposition": content_disposition_header(True, "games.pgn")},
    )


@router.get("/{int:game_id}", response=GameOut)
def get_game(request: AuthenticatedRequest, game_id: int) -> Game:
    """One of your games, with its moves."""
    return selectors.game(user=request.user, game_id=game_id)


@router.get("/{int:game_id}/pgn")
def download_game(request: AuthenticatedRequest, game_id: int) -> HttpResponse:
    """Download one game as a PGN file."""
    game = selectors.game(user=request.user, game_id=game_id)
    return HttpResponse(
        game.pgn,
        content_type=PGN_CONTENT_TYPE,
        headers={"Content-Disposition": content_disposition_header(True, _file_name(game))},
    )


def _file_name(game: Game) -> str:
    """E.g. "Carlsen, Magnus - Anna 2024.03.05.pgn"; unknown parts are left out."""
    players = f"{game.white or 'Unknown'} - {game.black or 'Unknown'}"
    date = "" if game.date_pgn.startswith("?") else f" {game.date_pgn}"
    return f"{players}{date}.pgn".replace("/", "-").replace("\\", "-")


@router.post("/imports", response={HTTPStatus.ACCEPTED: ImportOut})
def create_import(request: AuthenticatedRequest, file: File[UploadedFile]) -> Status[ImportRun]:
    """Upload a PGN file to import.

    The import runs in the background: poll GET /games/imports/{id} for its progress.
    """
    run = services.start_import(user=request.user, file_name=file.name or "", chunks=file.chunks())
    return Status(HTTPStatus.ACCEPTED, run)


@router.get("/imports", response=list[ImportOut])
@paginate(LimitOffset)
def list_imports(request: AuthenticatedRequest) -> QuerySet[ImportRun]:
    """Your imports, the newest first."""
    return selectors.import_runs(user=request.user)


@router.get("/imports/{import_run_id}", response=ImportOut)
def get_import(request: AuthenticatedRequest, import_run_id: int) -> ImportRun:
    """One of your imports, with its progress."""
    return selectors.import_run(user=request.user, import_run_id=import_run_id)


# ---------------------------------------------------------------- collections


@collections_router.get("", response=list[CollectionOut])
@paginate(LimitOffset)
def list_collections(request: AuthenticatedRequest) -> QuerySet[Collection]:
    """Your collections, by name."""
    return selectors.groups(Collection, user=request.user)


@collections_router.post("", response={HTTPStatus.CREATED: CollectionOut})
def create_collection(request: AuthenticatedRequest, data: CollectionIn) -> Status[Collection]:
    """Create a collection; 409 if you already have one with that name."""
    collection = services.create_group(
        Collection, user=request.user, name=data.name, description=data.description
    )
    return Status(HTTPStatus.CREATED, _collection(request, collection.pk))


@collections_router.get("/{int:collection_id}", response=CollectionOut)
def get_collection(request: AuthenticatedRequest, collection_id: int) -> Collection:
    return _collection(request, collection_id)


@collections_router.patch("/{int:collection_id}", response=CollectionOut)
def update_collection(
    request: AuthenticatedRequest, collection_id: int, data: CollectionPatch
) -> Collection:
    """Rename a collection or change its description."""
    collection = _collection(request, collection_id)
    services.update_group(collection, **data.dict(exclude_none=True))
    return _collection(request, collection_id)


@collections_router.delete("/{int:collection_id}", response={HTTPStatus.NO_CONTENT: None})
def delete_collection(request: AuthenticatedRequest, collection_id: int) -> Status[None]:
    """Delete a collection. Its games stay in your database."""
    _collection(request, collection_id).delete()
    return Status(HTTPStatus.NO_CONTENT, None)


@collections_router.post("/{int:collection_id}/games", response=CollectionOut)
def add_to_collection(
    request: AuthenticatedRequest, collection_id: int, data: GameIdsIn
) -> Collection:
    """Add games; 404 without adding any if one of them isn't yours."""
    services.add_games(_collection(request, collection_id), game_ids=data.game_ids)
    return _collection(request, collection_id)


@collections_router.delete("/{int:collection_id}/games", response=CollectionOut)
def remove_from_collection(
    request: AuthenticatedRequest, collection_id: int, game_ids: Query[list[int]]
) -> Collection:
    """Take games out of the collection, e.g. ?game_ids=1&game_ids=5."""
    services.remove_games(_collection(request, collection_id), game_ids=game_ids)
    return _collection(request, collection_id)


def _collection(request: AuthenticatedRequest, collection_id: int) -> Collection:
    return selectors.group(Collection, user=request.user, group_id=collection_id)


# ---------------------------------------------------------------- tags


@tags_router.get("", response=list[TagOut])
@paginate(LimitOffset)
def list_tags(request: AuthenticatedRequest) -> QuerySet[Tag]:
    """Your tags, by name."""
    return selectors.groups(Tag, user=request.user)


@tags_router.post("", response={HTTPStatus.CREATED: TagOut})
def create_tag(request: AuthenticatedRequest, data: TagIn) -> Status[Tag]:
    """Create a tag; 409 if you already have one with that name."""
    tag = services.create_group(Tag, user=request.user, name=data.name)
    return Status(HTTPStatus.CREATED, _tag(request, tag.pk))


@tags_router.patch("/{int:tag_id}", response=TagOut)
def rename_tag(request: AuthenticatedRequest, tag_id: int, data: TagIn) -> Tag:
    services.update_group(_tag(request, tag_id), name=data.name)
    return _tag(request, tag_id)


@tags_router.delete("/{int:tag_id}", response={HTTPStatus.NO_CONTENT: None})
def delete_tag(request: AuthenticatedRequest, tag_id: int) -> Status[None]:
    """Delete a tag. Its games stay in your database."""
    _tag(request, tag_id).delete()
    return Status(HTTPStatus.NO_CONTENT, None)


@tags_router.post("/{int:tag_id}/games", response=TagOut)
def tag_games(request: AuthenticatedRequest, tag_id: int, data: GameIdsIn) -> Tag:
    """Tag games; 404 without tagging any if one of them isn't yours."""
    services.add_games(_tag(request, tag_id), game_ids=data.game_ids)
    return _tag(request, tag_id)


@tags_router.delete("/{int:tag_id}/games", response=TagOut)
def untag_games(request: AuthenticatedRequest, tag_id: int, game_ids: Query[list[int]]) -> Tag:
    """Remove the tag from games, e.g. ?game_ids=1&game_ids=5."""
    services.remove_games(_tag(request, tag_id), game_ids=game_ids)
    return _tag(request, tag_id)


def _tag(request: AuthenticatedRequest, tag_id: int) -> Tag:
    return selectors.group(Tag, user=request.user, group_id=tag_id)
