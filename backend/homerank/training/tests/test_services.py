"""Finding puzzles in analysed games, and training them with FSRS."""

import io
import itertools
from datetime import UTC, datetime, time, timedelta

import pytest
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob
from pytest_django import Settings

from homerank.accounts.models import User
from homerank.analysis.models import GameAnalysis
from homerank.analysis.services import run_analysis, start_analysis
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.games.models import Game
from homerank.games.services import new_game, store_games
from homerank.training import services, tasks
from homerank.training.models import Puzzle, PuzzleScan, ReviewCard, ReviewLog
from homerank.training.services import (
    NotLatestReviewError,
    change_rating,
    queue_puzzle_scans,
    review,
    scan_game,
    suggested_rating,
)

pytestmark = pytest.mark.django_db

# Black's 3... Nf6?? allows mate in one, which White plays.
SCHOLARS_MATE = """\
[White "alice64"]
[Black "bob_b"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0
"""
_hashes = itertools.count()


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice", player_names=["alice64"])


@pytest.fixture
def quick(settings: Settings) -> None:
    settings.ANALYSIS_DEPTH = 10
    settings.PUZZLE_DEPTH = 12


def a_game(user: User, text: str = SCHOLARS_MATE) -> Game:
    (item,) = read_pgn(io.BytesIO(text.encode()))
    assert isinstance(item, PgnGame)
    store_games(user, [new_game(user, item)])
    return Game.objects.filter(user=user).latest("pk")


def analysed(user: User, game: Game) -> Game:
    (run,) = start_analysis(user=user, games=[game])
    run_analysis(analysis_run_id=run.pk)
    return game


def summary(game: Game) -> GameAnalysis:
    """A game's analysis summary, as if analysed: enough for the periodic job to pick it."""
    return GameAnalysis.objects.create(
        game=game, depth=18, engine="Stockfish 19", analysed_at=datetime.now(tz=UTC)
    )


def bare_game(user: User, user_color: str = "white") -> Game:
    return Game.objects.create(
        user=user,
        source=Game.Source.PGN,
        pgn="1. e4 *\n",
        result="*",
        date_pgn="????.??.??",
        time_class="unknown",
        ply_count=1,
        user_color=user_color,
        dedup_hash=f"{next(_hashes):064}",
    )


# ---------------------------------------------------------------- finding puzzles


@pytest.mark.engine
@pytest.mark.usefixtures("quick")
def test_finds_the_mate_the_user_found_after_a_blunder(alice: User) -> None:
    game = analysed(alice, a_game(alice))

    assert scan_game(game_id=game.pk) == 1

    puzzle = Puzzle.objects.get()
    assert (puzzle.user, puzzle.game, puzzle.ply, puzzle.kind) == (alice, game, 6, "found")
    assert puzzle.solution == ["h5f7"]
    assert puzzle.themes == ["mateIn1"]
    assert puzzle.last_move_uci == "g8f6"
    assert puzzle.fen.startswith("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/")
    card = ReviewCard.objects.get(puzzle=puzzle)
    assert card.due_at <= timezone.now()  # new cards are due at once
    assert PuzzleScan.objects.get(game=game).puzzles_found == 1


@pytest.mark.engine
@pytest.mark.usefixtures("quick")
def test_a_game_is_searched_once(alice: User) -> None:
    game = analysed(alice, a_game(alice))
    scan_game(game_id=game.pk)

    assert scan_game(game_id=game.pk) == 0
    assert Puzzle.objects.count() == 1


def test_a_game_without_complete_analysis_gives_no_puzzles(alice: User) -> None:
    game = a_game(alice)  # not analysed

    assert scan_game(game_id=game.pk) == 0
    assert PuzzleScan.objects.get(game=game).puzzles_found == 0


def test_queues_searches_of_analysed_games_the_user_played(alice: User) -> None:
    wanted = bare_game(alice)
    summary(wanted)
    summary(bare_game(alice, user_color=""))  # not the user's game
    bare_game(alice)  # not analysed
    searched = bare_game(alice)
    summary(searched)
    PuzzleScan.objects.create(game=searched, puzzles_found=0)

    assert queue_puzzle_scans() == 1

    (job,) = ProcrastinateJob.objects.filter(task_name="homerank.training.tasks.scan_game")
    assert job.args == {"game_id": wanted.pk}
    assert job.queue_name == "analysis"
    assert job.lock == "engine-0"  # shares the engine with analyses


def test_a_queued_search_isnt_queued_again(alice: User) -> None:
    summary(bare_game(alice))
    queue_puzzle_scans()

    assert queue_puzzle_scans() == 0
    assert ProcrastinateJob.objects.filter(task_name__endswith="scan_game").count() == 1


def test_searches_wait_for_the_analysis_hours(
    alice: User, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary(bare_game(alice))
    settings.ANALYSIS_HOURS = (time(23, 0), time(7, 0))
    monkeypatch.setattr(timezone, "now", lambda: datetime(2026, 10, 23, 12, tzinfo=UTC))

    assert queue_puzzle_scans() == 0


def test_the_jobs_run_the_services(alice: User) -> None:
    game = bare_game(alice)
    summary(game)

    tasks.queue_puzzle_scans(timestamp=0)
    tasks.scan_game(game_id=game.pk)

    assert PuzzleScan.objects.filter(game=game).exists()


# ---------------------------------------------------------------- training


@pytest.mark.parametrize(
    ("correct", "elapsed_ms", "moves", "expected"),
    [
        (False, 1_000, 1, ReviewLog.Rating.AGAIN),
        (True, 4_000, 1, ReviewLog.Rating.EASY),
        (True, 9_000, 2, ReviewLog.Rating.EASY),  # 4.5 s per move
        (True, 5_000, 1, ReviewLog.Rating.EASY),
        (True, 15_000, 1, ReviewLog.Rating.GOOD),
        (True, 12_000, 1, ReviewLog.Rating.GOOD),
        (True, 40_000, 1, ReviewLog.Rating.HARD),
    ],
)
def test_the_rating_follows_from_the_solve(
    correct: bool, elapsed_ms: int, moves: int, expected: int
) -> None:
    rating = suggested_rating(correct=correct, elapsed_ms=elapsed_ms, solver_moves=moves)

    assert rating == expected


def a_card(user: User) -> ReviewCard:
    game = bare_game(user)
    puzzle = Puzzle.objects.create(
        user=user,
        game=game,
        ply=0,
        kind="missed",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        solution=["e2e4"],
        win_swing=30.0,
    )
    return services._new_card(puzzle)


def test_a_review_schedules_the_puzzle_again(alice: User) -> None:
    card = a_card(alice)
    before = card.fsrs_state

    log = review(card, correct=True, elapsed_ms=3_000)

    card.refresh_from_db()
    assert (log.rating, log.correct, log.elapsed_ms) == (ReviewLog.Rating.EASY, True, 3_000)
    assert log.card_state_before == before
    assert card.due_at > timezone.now() + timedelta(days=1)  # easy: not again today
    assert card.fsrs_state["last_review"] is not None


def test_a_failed_puzzle_comes_back_soon(alice: User) -> None:
    card = a_card(alice)

    review(card, correct=False, elapsed_ms=3_000)

    card.refresh_from_db()
    assert card.due_at < timezone.now() + timedelta(minutes=15)


def test_the_latest_rating_can_be_changed(alice: User) -> None:
    card = a_card(alice)
    log = review(card, correct=True, elapsed_ms=3_000)  # Easy

    change_rating(log, rating=ReviewLog.Rating.AGAIN)

    card.refresh_from_db()
    log.refresh_from_db()
    assert log.rating == ReviewLog.Rating.AGAIN
    assert card.due_at < timezone.now() + timedelta(minutes=15)
    assert card.fsrs_state["step"] is not None


def test_a_changed_rating_counts_as_if_given_in_the_first_place(alice: User) -> None:
    changed, direct = a_card(alice), a_card(alice)

    change_rating(review(changed, correct=False, elapsed_ms=12_000), rating=ReviewLog.Rating.GOOD)
    review(direct, correct=True, elapsed_ms=12_000)  # Good

    changed.refresh_from_db()
    direct.refresh_from_db()
    for key in ("state", "step", "stability", "difficulty"):
        assert changed.fsrs_state[key] == pytest.approx(direct.fsrs_state[key])


def test_only_the_latest_rating_can_be_changed(alice: User) -> None:
    card = a_card(alice)
    first = review(card, correct=True, elapsed_ms=3_000)
    review(card, correct=True, elapsed_ms=3_000)

    with pytest.raises(NotLatestReviewError):
        change_rating(first, rating=ReviewLog.Rating.HARD)
