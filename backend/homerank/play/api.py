from http import HTTPStatus

from django.db.models import QuerySet
from django.utils import timezone
from ninja import Router, Status

from homerank.accounts.auth import AuthenticatedRequest
from homerank.play import selectors, services
from homerank.play.models import BotGame
from homerank.play.schemas import BotGameOut, GameIn, MoveIn, OpponentOut, SavedOut

router = Router(tags=["play"])


@router.get("/opponents", response=list[OpponentOut])
def opponents(request: AuthenticatedRequest) -> list[dict[str, object]]:
    """The bots and the ratings they play at: Maia's are Lichess ratings, Stockfish's are on
    an engine scale (see ADR 0017)."""
    return [
        {"opponent": opponent, "min_elo": low, "max_elo": high}
        for opponent, (low, high) in services.ELO_RANGES.items()
    ]


@router.get("/games", response=list[BotGameOut])
def list_games(request: AuthenticatedRequest) -> QuerySet[BotGame]:
    """Your latest 100 games against bots, newest first."""
    return selectors.games(user=request.user)


@router.post("/games", response={HTTPStatus.CREATED: BotGameOut})
def start_game(request: AuthenticatedRequest, data: GameIn) -> Status[BotGame]:
    """Start a game from a position. If the bot is to move there, it has moved already."""
    setup = services.Setup(
        start_fen=data.start_fen,
        start_label=data.start_label,
        user_color=data.user_color,
        opponent=data.opponent,
        opponent_elo=data.opponent_elo,
        clock_base_ms=data.clock.base_seconds * 1000 if data.clock else None,
        clock_increment_ms=data.clock.increment_seconds * 1000 if data.clock else None,
    )
    return Status(HTTPStatus.CREATED, services.start_game(user=request.user, setup=setup))


@router.get("/games/{int:game_id}", response=BotGameOut)
def get_game(request: AuthenticatedRequest, game_id: int) -> BotGame:
    """A game; one whose clock ran out meanwhile is finished first."""
    return services.settle_clock(_game(request, game_id), now=timezone.now())


@router.post("/games/{int:game_id}/moves", response=BotGameOut)
def play_move(request: AuthenticatedRequest, game_id: int, data: MoveIn) -> BotGame:
    """Play your move; the answer has the bot's reply, unless the game ended."""
    return services.play_move(_game(request, game_id), move_uci=data.move_uci)


@router.post("/games/{int:game_id}/take-back", response=BotGameOut)
def take_back(request: AuthenticatedRequest, game_id: int) -> BotGame:
    """Take back your last move and the bot's reply (untimed games only)."""
    return services.take_back(_game(request, game_id))


@router.post("/games/{int:game_id}/resign", response=BotGameOut)
def resign(request: AuthenticatedRequest, game_id: int) -> BotGame:
    return services.resign(_game(request, game_id))


@router.post("/games/{int:game_id}/save", response=SavedOut)
def save(request: AuthenticatedRequest, game_id: int) -> dict[str, int]:
    """Add the game to your games, where it is analysed and searched like any other."""
    return {"game_id": services.save_to_games(_game(request, game_id)).pk}


@router.delete("/games/{int:game_id}", response={HTTPStatus.NO_CONTENT: None})
def delete_game(request: AuthenticatedRequest, game_id: int) -> Status[None]:
    """Delete a game against a bot. A copy saved among your games stays."""
    _game(request, game_id).delete()
    return Status(HTTPStatus.NO_CONTENT, None)


def _game(request: AuthenticatedRequest, game_id: int) -> BotGame:
    return selectors.game(user=request.user, game_id=game_id)
