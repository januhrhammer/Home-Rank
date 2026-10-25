"""Starting, running and stopping novelty searches (ADR 0022)."""

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from http import HTTPStatus

import chess
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from procrastinate.contrib.django import app

from homerank.accounts.models import User
from homerank.core.errors import DomainError
from homerank.engine.maia import load
from homerank.engine.novelty import (
    EnginePool,
    Evaluator,
    MaiaModel,
    OpponentModel,
    Search,
    Settings,
    StockfishEvaluator,
    Try,
)
from homerank.engine.uci import open_engine
from homerank.explorer.selectors import ReferenceFilters, reference_explorer
from homerank.novelty.models import NoveltySearch, NoveltyTry, RatingKind, SearchStatus
from homerank.reference.models import ReferenceDatabase

# How often a running search looks whether it was cancelled, in seconds.
CANCEL_CHECK_SECONDS = 5


class InvalidStartError(DomainError):
    status = HTTPStatus.UNPROCESSABLE_ENTITY
    detail = "This isn't a valid position to search from."


class SearchFinishedError(DomainError):
    status = HTTPStatus.CONFLICT
    detail = "This search has finished already."


# ---------------------------------------------------------------- the opponent's rating

# Lichess ratings run above FIDE and DWZ ratings at club level (ADR 0022): by these many points
# up to LOW, then less and less, down to TOP_OFFSET from TOP on. A rough rule: the form shows the
# result, and the user can change it.
OFFSETS = {RatingKind.LICHESS: 0, RatingKind.FIDE: 200, RatingKind.DWZ: 250}
LOW, TOP, TOP_OFFSET = 1500, 2300, 100


def lichess_rating(rating: int, kind: str) -> int:
    """The Lichess rating Maia should play at for an opponent of this rating."""
    offset = OFFSETS[RatingKind(kind)]
    if offset == 0:
        return rating
    if rating <= LOW:
        return rating + offset
    if rating >= TOP:
        return rating + TOP_OFFSET
    share = (rating - LOW) / (TOP - LOW)
    return rating + round(offset + share * (TOP_OFFSET - offset))


# ---------------------------------------------------------------- starting and stopping


def start_search(  # noqa: PLR0913 - the form's fields
    *,
    user: User,
    fen: str,
    moves: list[str],
    label: str,
    side: str,
    rating: int,
    rating_kind: str,
    budget_cp: int,
    limit_minutes: int,
    elo: int | None = None,
) -> NoveltySearch:
    """Queue a search; `elo` overrides the Lichess rating worked out from `rating`. One search
    runs at a time on the server: others wait their turn."""
    try:
        board = chess.Board(fen)
    except ValueError as error:
        raise InvalidStartError from error
    if not board.is_valid() or board.is_game_over():
        raise InvalidStartError
    with transaction.atomic():
        search = NoveltySearch.objects.create(
            user=user,
            start_fen=board.fen(),
            start_moves=moves,
            start_label=label,
            side=side,
            rating=rating,
            rating_kind=rating_kind,
            elo=elo if elo is not None else lichess_rating(rating, rating_kind),
            budget_cp=budget_cp,
            limit_minutes=min(limit_minutes, settings.NOVELTY_MAX_MINUTES),
        )
        task = app.configure_task(
            "homerank.novelty.tasks.novelty_search", lock="novelty", queue="novelty"
        )
        search.job_id = task.defer(search_id=search.pk)
        search.save(update_fields=["job_id"])
    return search


def cancel_search(search: NoveltySearch) -> NoveltySearch:
    """Stop a search: one waiting doesn't start; one running stops within seconds, keeping the
    tries of its last finished step."""
    if search.status not in (SearchStatus.QUEUED, SearchStatus.RUNNING):
        raise SearchFinishedError
    with transaction.atomic():
        search = NoveltySearch.objects.select_for_update().get(pk=search.pk)
        if search.status == SearchStatus.QUEUED:
            search.status = SearchStatus.CANCELLED
            search.finished_at = timezone.now()
        search.cancel_requested = True
        search.save(update_fields=["status", "finished_at", "cancel_requested"])
    return search


# ---------------------------------------------------------------- running


def run_search(
    search_id: int,
    *,
    engines: list[Evaluator] | None = None,
    model: OpponentModel | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """The job: search until the time limit, a cancel or the last step, storing the tries after
    each step. Without `engines` and `model`, Stockfish (NOVELTY_ENGINES of them) and Maia."""
    search = NoveltySearch.objects.get(pk=search_id)
    if search.status != SearchStatus.QUEUED:
        return  # cancelled before it started
    search.status = SearchStatus.RUNNING
    search.started_at = timezone.now()
    search.save(update_fields=["status", "started_at"])
    deadline = clock() + search.limit_minutes * 60
    try:
        with _evaluators(engines) as evaluators, _CancelWatch(search.pk) as cancelled:
            found = Search(
                _start_board(search),
                Settings(
                    us=chess.WHITE if search.side == "white" else chess.BLACK,
                    elo=search.elo,
                    budget_cp=search.budget_cp,
                ),
                EnginePool(evaluators),
                model or MaiaModel(load(settings.MAIA_PATH)),
                should_stop=lambda: clock() >= deadline or cancelled.is_set(),
            )
            for own_moves, tries in found.steps():
                _store(search, own_moves, tries)
    except Exception as error:
        search.status = SearchStatus.FAILED
        search.error = str(error) or type(error).__name__
        search.finished_at = timezone.now()
        search.save(update_fields=["status", "error", "finished_at"])
        raise
    search.status = SearchStatus.CANCELLED if cancelled.is_set() else SearchStatus.DONE
    search.finished_at = timezone.now()
    search.save(update_fields=["status", "finished_at"])


class _CancelWatch:
    """A thread that looks every few seconds whether the search was cancelled, and sets the
    event it gives if so. The search's own threads only read the event: database connections
    belong to threads, and one is enough."""

    def __init__(self, search_id: int) -> None:
        self.search_id = search_id
        self.cancelled = threading.Event()
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._watch, daemon=True)

    def __enter__(self) -> threading.Event:
        self.thread.start()
        return self.cancelled

    def __exit__(self, *_: object) -> None:
        self.done.set()
        self.thread.join()

    def _watch(self) -> None:
        try:
            while not self.done.wait(CANCEL_CHECK_SECONDS):
                if NoveltySearch.objects.filter(pk=self.search_id, cancel_requested=True).exists():
                    self.cancelled.set()
                    return
        finally:
            connection.close()  # this thread's own connection


@contextmanager
def _evaluators(given: list[Evaluator] | None) -> Iterator[list[Evaluator]]:
    """The given evaluators, or NOVELTY_ENGINES single-thread Stockfish engines, stopped after."""
    if given is not None:
        yield given
        return
    with ExitStack() as stack:
        yield [
            StockfishEvaluator(
                stack.enter_context(
                    open_engine(settings.STOCKFISH_PATH, threads=1, hash_mb=settings.ENGINE_HASH_MB)
                )
            )
            for _ in range(settings.NOVELTY_ENGINES)
        ]


def _start_board(search: NoveltySearch) -> chess.Board:
    """The start position, with the moves that led there if they do: Maia reads the positions
    before the one it moves in."""
    board = chess.Board()
    try:
        for uci in search.start_moves:
            board.push_uci(uci)
    except ValueError:
        return chess.Board(search.start_fen)
    return board if board.fen() == search.start_fen else chess.Board(search.start_fen)


def _store(search: NoveltySearch, own_moves: int, tries: list[Try]) -> None:
    """Replace the search's tries with a step's, each with how often a reference database has
    the position after it."""
    reference = (
        ReferenceDatabase.objects.filter(status=ReferenceDatabase.Status.READY)
        .order_by("name")
        .first()
    )
    rows = []
    for rank, found in enumerate(tries):
        board = chess.Board(search.start_fen)
        for uci in [*found.line, found.uci]:
            board.push_uci(uci)
        games = (
            reference_explorer(
                database=reference, fen=board.fen(), filters=ReferenceFilters()
            ).games
            if reference is not None
            else None
        )
        rows.append(
            NoveltyTry(
                search=search,
                rank=rank,
                line=found.line,
                uci=found.uci,
                san=found.san,
                cp=found.cp,
                practical=found.practical,
                best_san=found.best_san,
                best_practical=found.best_practical,
                reach=found.reach,
                refutation=[
                    {"san": step.san, "uci": step.uci, "found": step.found}
                    for step in found.refutation
                ],
                reference_games=games,
            )
        )
    with transaction.atomic():
        search.tries.all().delete()
        NoveltyTry.objects.bulk_create(rows)
        search.own_moves = own_moves
        search.save(update_fields=["own_moves"])
