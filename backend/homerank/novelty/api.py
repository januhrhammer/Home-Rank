from http import HTTPStatus

from django.db.models import QuerySet
from ninja import Query, Router, Status
from ninja.pagination import paginate

from homerank.accounts.auth import AuthenticatedRequest
from homerank.core.pagination import LimitOffset
from homerank.novelty import selectors, services
from homerank.novelty.models import NoveltySearch, RatingKind
from homerank.novelty.schemas import RatingOut, SearchDetailOut, SearchIn, SearchOut

router = Router(tags=["novelty"])


@router.get("/searches", response=list[SearchOut])
@paginate(LimitOffset)
def list_searches(request: AuthenticatedRequest) -> QuerySet[NoveltySearch]:
    """Your novelty searches, newest first."""
    return selectors.searches(user=request.user)


@router.post("/searches", response={HTTPStatus.CREATED: SearchOut})
def start_search(request: AuthenticatedRequest, data: SearchIn) -> Status[NoveltySearch]:
    """Queue a search for tries from a position (ADR 0022). One runs at a time; it stores what
    it found after each step, until its time limit."""
    search = services.start_search(
        user=request.user,
        fen=data.fen,
        moves=data.moves,
        label=data.label,
        side=data.side,
        rating=data.rating,
        rating_kind=data.rating_kind,
        budget_cp=data.budget_cp,
        limit_minutes=data.limit_minutes,
        elo=data.elo,
    )
    return Status(HTTPStatus.CREATED, search)


@router.get("/searches/{int:search_id}", response=SearchDetailOut)
def get_search(request: AuthenticatedRequest, search_id: int) -> dict[str, object]:
    """A search with the tries of its last finished step, the best first."""
    search = selectors.search(user=request.user, search_id=search_id)
    return {**SearchOut.from_orm(search).dict(), "tries": list(selectors.tries(search))}


@router.post("/searches/{int:search_id}/cancel", response=SearchOut)
def cancel_search(request: AuthenticatedRequest, search_id: int) -> NoveltySearch:
    """Stop a search; it keeps the tries found so far. 409 if it has ended."""
    return services.cancel_search(selectors.search(user=request.user, search_id=search_id))


@router.delete("/searches/{int:search_id}", response={HTTPStatus.NO_CONTENT: None})
def delete_search(request: AuthenticatedRequest, search_id: int) -> Status[None]:
    """Delete a search that has ended; 409 while it waits or runs (cancel it first)."""
    services.delete_search(selectors.search(user=request.user, search_id=search_id))
    return Status(HTTPStatus.NO_CONTENT, None)


@router.get("/rating", response=RatingOut)
def rating(
    request: AuthenticatedRequest, rating: Query[int], kind: Query[RatingKind] = RatingKind.FIDE
) -> dict[str, int]:
    """The Lichess rating Maia would play at for an opponent of this rating, to show in the
    form before starting."""
    return {"elo": services.lichess_rating(rating, kind)}
