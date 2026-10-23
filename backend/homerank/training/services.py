"""Finding puzzles in a user's analysed games, and scheduling their training with FSRS.

queue_puzzle_scans (periodic) queues searches of analysed games; scan_game, which the job
calls, asks the engine for puzzles in one game. review records how the user did on a puzzle
and schedules it again. See ADR 0014.
"""

import io
from http import HTTPStatus

import chess
import chess.engine
import chess.pgn
import fsrs
import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from procrastinate import exceptions as procrastinate_exceptions
from procrastinate.contrib.django import app

from homerank.analysis.models import PositionEval
from homerank.analysis.services import within_analysis_hours
from homerank.core.errors import DomainError
from homerank.engine.tactics import find_candidates, solve, themes
from homerank.engine.uci import open_engine
from homerank.games.models import Game
from homerank.repertoire.models import RepertoireMove
from homerank.training.models import Puzzle, PuzzleScan, ReviewCard, ReviewLog

logger = structlog.get_logger(__name__)

# Games queued for a search per run of the periodic job at most.
SCANS_PER_RUN = 20
# Solve times per move of the user's that make a correct solve "Easy" or "Good" (else "Hard").
EASY_MS_PER_MOVE = 5_000
GOOD_MS_PER_MOVE = 15_000

_scheduler = fsrs.Scheduler()


# ---------------------------------------------------------------- finding puzzles


def queue_puzzle_scans() -> int:
    """Queue searches of analysed games the users played that were never searched, newest
    first. Like automatic analyses, only within ANALYSIS_HOURS. Returns how many were queued.
    """
    if not within_analysis_hours(timezone.now()):
        return 0
    games = (
        Game.objects.filter(analysis__isnull=False, puzzle_scan__isnull=True)
        .exclude(user_color="")
        .order_by("-analysis__analysed_at")[:SCANS_PER_RUN]
    )
    queued = 0
    for game in games:
        slot = game.pk % settings.ANALYSIS_CONCURRENCY
        task = app.configure_task(
            "homerank.training.tasks.scan_game",
            # The engine slot of the game's analyses, which share the engine's CPU time.
            lock=f"engine-{slot}",
            # Queued once: the job runs every few minutes, the search may take longer.
            queueing_lock=f"scan-{game.pk}",
            queue="analysis",
        )
        try:
            with transaction.atomic():  # a savepoint: the refused insert doesn't end the rest
                task.defer(game_id=game.pk)
        except procrastinate_exceptions.AlreadyEnqueued:
            continue
        queued += 1
    logger.info("Puzzle searches queued", count=queued)
    return queued


def scan_game(*, game_id: int) -> int:
    """Search one analysed game for puzzles and store them, each with a new card. Returns
    how many were found. Called by the job, not during a request."""
    game = Game.objects.select_related("user").get(pk=game_id)
    if PuzzleScan.objects.filter(game=game).exists():
        return 0
    parsed = chess.pgn.read_game(io.StringIO(game.pgn))
    evals = list(PositionEval.objects.filter(game=game).order_by("ply"))
    if parsed is None or len(evals) != game.ply_count + 1 or game.user_color == "":
        found: list[Puzzle] = []  # incomplete analysis or not the user's game: nothing to find
    else:
        found = _find_puzzles(game, parsed, evals)
    with transaction.atomic():
        for puzzle in found:
            puzzle.save()
            _new_card(puzzle)
        PuzzleScan.objects.create(game=game, puzzles_found=len(found))
    logger.info("Game searched for puzzles", game_id=game.pk, puzzles=len(found))
    return len(found)


def _find_puzzles(game: Game, parsed: chess.pgn.Game, evals: list[PositionEval]) -> list[Puzzle]:
    boards = [parsed.board()]
    moves = []
    for move in parsed.mainline_moves():
        moves.append(move.uci())
        board = boards[-1].copy()
        board.push(move)
        boards.append(board)
    candidates = find_candidates(
        [e.win_percent for e in evals],
        moves,
        [e.best_move_uci for e in evals],
        user_white=game.user_color == "white",
        white_first=boards[0].turn == chess.WHITE,
    )
    if not candidates:
        return []
    puzzles = []
    limit = chess.engine.Limit(depth=settings.PUZZLE_DEPTH)
    with open_engine(
        settings.STOCKFISH_PATH, threads=settings.ENGINE_THREADS, hash_mb=settings.ENGINE_HASH_MB
    ) as engine:
        for candidate in candidates:
            board = boards[candidate.ply]
            solution = solve(engine, board, limit)
            if not solution:
                continue
            puzzles.append(
                Puzzle(
                    user=game.user,
                    game=game,
                    ply=candidate.ply,
                    kind=candidate.kind,
                    fen=board.fen(),
                    last_move_uci=moves[candidate.ply - 1] if candidate.ply > 0 else "",
                    solution=solution,
                    themes=themes(board, solution),
                    win_swing=candidate.win_swing,
                )
            )
    return puzzles


def _new_card(puzzle: Puzzle) -> ReviewCard:
    card = fsrs.Card()  # due now
    return ReviewCard.objects.create(
        user=puzzle.user, puzzle=puzzle, fsrs_state=card.to_dict(), due_at=card.due
    )


def new_repertoire_cards(moves: list[RepertoireMove]) -> None:
    """Cards for the user's own moves in a repertoire (ADR 0016), due now."""
    card = fsrs.Card()
    ReviewCard.objects.bulk_create(
        ReviewCard(
            user_id=move.repertoire.user_id,
            card_type=ReviewCard.CardType.REPERTOIRE,
            repertoire_move=move,
            fsrs_state=card.to_dict(),
            due_at=card.due,
        )
        for move in moves
    )


# ---------------------------------------------------------------- training


def suggested_rating(*, correct: bool, elapsed_ms: int, solver_moves: int) -> int:
    """FSRS's rating for a solve: a wrong move is Again; solved, the time per move of the
    user's decides between Easy, Good and Hard."""
    if not correct:
        return ReviewLog.Rating.AGAIN
    per_move = elapsed_ms / max(1, solver_moves)
    if per_move <= EASY_MS_PER_MOVE:
        return ReviewLog.Rating.EASY
    if per_move <= GOOD_MS_PER_MOVE:
        return ReviewLog.Rating.GOOD
    return ReviewLog.Rating.HARD


def review(card: ReviewCard, *, correct: bool, elapsed_ms: int) -> ReviewLog:
    """Record an answer to the card and schedule it again with the suggested rating. A
    repertoire move is "Good" when right on the first try, else "Again" (ADR 0016)."""
    if card.puzzle is not None:
        rating = suggested_rating(
            correct=correct,
            elapsed_ms=elapsed_ms,
            solver_moves=(len(card.puzzle.solution) + 1) // 2,
        )
    else:
        rating = ReviewLog.Rating.GOOD if correct else ReviewLog.Rating.AGAIN
    with transaction.atomic():
        log = ReviewLog(
            card=card,
            rating=rating,
            correct=correct,
            elapsed_ms=elapsed_ms,
            card_state_before=card.fsrs_state,
        )
        _schedule(card, log)
        log.save()
    return log


class NotLatestReviewError(DomainError):
    status = HTTPStatus.CONFLICT
    detail = "Only the latest review of a card can be changed."


def change_rating(log: ReviewLog, *, rating: int) -> ReviewLog:
    """Change the rating of the card's latest review: it is scheduled again from its state
    before that review."""
    card = log.card
    if card.logs.order_by("-reviewed_at", "-pk").first() != log:
        raise NotLatestReviewError
    with transaction.atomic():
        log.rating = rating
        card.fsrs_state = log.card_state_before
        _schedule(card, log)
        log.save(update_fields=["rating"])
    return log


def _schedule(card: ReviewCard, log: ReviewLog) -> None:
    """Move the card to its next due time for the log's rating, with FSRS."""
    state = fsrs.Card.from_dict(card.fsrs_state)
    state, _ = _scheduler.review_card(
        state, fsrs.Rating(log.rating), timezone.now(), review_duration=log.elapsed_ms
    )
    card.fsrs_state = state.to_dict()
    card.due_at = state.due
    card.save(update_fields=["fsrs_state", "due_at"])
