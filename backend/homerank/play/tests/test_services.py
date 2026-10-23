from datetime import UTC, datetime, timedelta
from typing import Any

import chess
import pytest

from homerank.accounts.models import User
from homerank.chesslib.players import Side
from homerank.core.errors import DomainError
from homerank.games.models import Game
from homerank.play import services
from homerank.play.models import BotGame, Opponent
from homerank.play.services import Setup

pytestmark = [pytest.mark.django_db, pytest.mark.maia]

START = chess.STARTING_FEN
# White mates with Rd8.
BACK_RANK = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"
# Black has only its king left: it can't win on time.
LONE_KING = "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"
NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice", player_names=["Alice Example"])


def start(user: User, **fields: Any) -> BotGame:
    values: dict[str, Any] = {
        "start_fen": START,
        "user_color": Side.WHITE,
        "opponent": Opponent.MAIA,
        "opponent_elo": 1500,
        **fields,
    }
    return services.start_game(user=user, setup=Setup(**values))


def timed(user: User, **fields: Any) -> BotGame:
    """A 1+0 game whose clock started at NOW."""
    game = start(user, clock_base_ms=60_000, clock_increment_ms=0, **fields)
    game.turn_started_at = NOW
    game.save()
    return game


# ---------------------------------------------------------------- starting


def test_with_white_the_user_moves_first(alice: User) -> None:
    game = start(alice)

    assert (game.moves, game.status, game.result) == ([], "playing", "")


def test_with_black_the_bot_moves_at_once(alice: User) -> None:
    game = start(alice, user_color=Side.BLACK)

    assert len(game.moves) == len(game.move_ms) == 1
    assert chess.Move.from_uci(game.moves[0]) in chess.Board().legal_moves


@pytest.mark.parametrize(
    "fields",
    [
        {"start_fen": "not a position"},
        {"start_fen": "8/8/8/8/8/8/8/8 w - - 0 1"},  # no kings
        {"start_fen": "3R2k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1"},  # White to move, Black in check
        {"start_fen": "3R2k1/5ppp/8/8/8/8/5PPP/6K1 b - - 1 1"},  # mate: nothing to play
        {"opponent_elo": 700},
        {"opponent": Opponent.STOCKFISH, "opponent_elo": 1000},
        {"clock_base_ms": 60_000},  # no increment
        {"clock_base_ms": 0, "clock_increment_ms": 0},
        {"clock_base_ms": 4 * 3_600_000, "clock_increment_ms": 0},
    ],
)
def test_a_game_needs_a_playable_position_a_rating_in_range_and_a_whole_clock(
    alice: User, fields: dict[str, Any]
) -> None:
    with pytest.raises(DomainError):
        start(alice, **fields)

    assert not BotGame.objects.exists()


# ---------------------------------------------------------------- playing


def test_the_bot_answers_the_users_move(alice: User) -> None:
    game = start(alice)
    game.turn_started_at = NOW
    game.save()

    game = services.play_move(game, move_uci="e2e4", now=NOW + timedelta(seconds=3))

    # The user's move, after 3 seconds, and the bot's answer.
    assert (game.moves[0], game.move_ms[0], len(game.moves)) == ("e2e4", 3000, 2)
    assert services.board_of(game).turn == chess.WHITE


def test_an_illegal_move_changes_nothing(alice: User) -> None:
    game = start(alice)

    for move in ("e2e5", "e7e5", "nonsense"):
        with pytest.raises(services.IllegalMoveError):
            services.play_move(game, move_uci=move)

    game.refresh_from_db()
    assert game.moves == []


def test_the_user_cant_move_for_the_bot(alice: User) -> None:
    # Stored with the bot to move, as it would be for a moment while it computes.
    game = BotGame.objects.create(
        user=alice,
        start_fen=START,
        user_color=Side.BLACK,
        opponent=Opponent.MAIA,
        opponent_elo=1500,
    )

    with pytest.raises(services.NotYourTurnError):
        services.play_move(game, move_uci="e2e4")


def test_mate_ends_the_game_and_the_bot_doesnt_move(alice: User) -> None:
    game = start(alice, start_fen=BACK_RANK)

    game = services.play_move(game, move_uci="d1d8", now=NOW)

    assert game.moves == ["d1d8"]
    assert (game.status, game.result, game.termination) == ("finished", "1-0", "checkmate")
    assert game.finished_at == NOW
    with pytest.raises(services.GameFinishedError):
        services.play_move(game, move_uci="g1f1")


def test_resigning_loses(alice: User) -> None:
    game = services.resign(start(alice, user_color=Side.BLACK))

    assert (game.status, game.result, game.termination) == ("finished", "1-0", "resignation")
    with pytest.raises(services.GameFinishedError):
        services.resign(game)


# ---------------------------------------------------------------- the clock


def test_untimed_games_have_no_clock(alice: User) -> None:
    assert services.clock_at(start(alice), NOW) is None


def test_each_side_has_its_base_time_plus_increments_minus_its_moves(alice: User) -> None:
    game = BotGame(
        user=alice,
        start_fen=START,
        user_color=Side.WHITE,
        opponent=Opponent.MAIA,
        opponent_elo=1500,
        clock_base_ms=60_000,
        clock_increment_ms=2_000,
        moves=["e2e4", "e7e5", "g1f3"],
        move_ms=[5_000, 100, 7_000],
        turn_started_at=NOW,  # Black's turn since NOW
    )

    clock = services.clock_at(game, NOW + timedelta(seconds=4))

    assert clock == services.Clock(
        white_ms=60_000 + 2 * 2_000 - 5_000 - 7_000,
        black_ms=60_000 + 2_000 - 100 - 4_000,
    )


def test_from_a_position_with_black_to_move_black_moved_first(alice: User) -> None:
    game = BotGame(
        user=alice,
        start_fen="4k3/8/8/8/8/8/4P3/4K3 b - - 0 1",
        user_color=Side.BLACK,
        opponent=Opponent.MAIA,
        opponent_elo=1500,
        clock_base_ms=60_000,
        clock_increment_ms=0,
        moves=["e8d8", "e2e4"],
        move_ms=[5_000, 100],
        turn_started_at=NOW,
    )

    assert services.clock_at(game, NOW) == services.Clock(white_ms=59_900, black_ms=55_000)


def test_a_move_after_the_time_ran_out_loses_on_time(alice: User) -> None:
    game = timed(alice)

    game = services.play_move(game, move_uci="e2e4", now=NOW + timedelta(seconds=61))

    assert game.moves == []  # not played
    assert (game.status, game.result, game.termination) == ("finished", "0-1", "timeout")


def test_running_out_of_time_against_a_lone_king_is_a_draw(alice: User) -> None:
    game = timed(alice, start_fen=LONE_KING)

    game = services.play_move(game, move_uci="e2e4", now=NOW + timedelta(seconds=61))

    assert (game.result, game.termination) == ("1/2-1/2", "timeout")


def test_a_game_left_alone_is_lost_on_time_when_next_looked_at(alice: User) -> None:
    game = timed(alice)

    services.settle_clock(game, now=NOW + timedelta(seconds=30))
    game.refresh_from_db()
    assert game.status == "playing"

    services.settle_clock(game, now=NOW + timedelta(seconds=61))
    game.refresh_from_db()
    assert (game.status, game.result) == ("finished", "0-1")


# ---------------------------------------------------------------- taking back


def test_taking_back_undoes_the_users_move_and_the_bots_answer(alice: User) -> None:
    game = services.play_move(start(alice), move_uci="e2e4")

    game = services.take_back(game)

    assert (game.moves, game.move_ms) == ([], [])


def test_with_black_taking_back_keeps_the_bots_first_move(alice: User) -> None:
    game = start(alice, user_color=Side.BLACK)
    first = game.moves[0]
    reply = next(iter(services.board_of(game).legal_moves)).uci()
    game = services.play_move(game, move_uci=reply)

    game = services.take_back(game)

    assert game.moves == [first]
    with pytest.raises(services.NoTakeBackError):
        services.take_back(game)  # nothing of the user's left


def test_no_taking_back_with_a_clock_or_after_the_game(alice: User) -> None:
    timed_game = services.play_move(timed(alice), move_uci="e2e4", now=NOW)
    finished = services.resign(services.play_move(start(alice), move_uci="e2e4"))

    for game in (timed_game, finished):
        with pytest.raises(services.NoTakeBackError):
            services.take_back(game)


# ---------------------------------------------------------------- into the user's games


def test_a_finished_game_is_saved_as_one_of_the_users_games(alice: User) -> None:
    game = services.play_move(start(alice, start_fen=BACK_RANK), move_uci="d1d8")

    saved = services.save_to_games(game)

    assert saved.user == alice
    assert (saved.white, saved.black, saved.result) == ("Alice Example", "Maia 1500", "1-0")
    assert saved.user_color == "white"  # found by the user's player name
    assert saved.event == "Practice against Maia 1500"
    assert '[FEN "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"]' in saved.pgn
    assert saved.pgn.rstrip().endswith("1. Rd8# 1-0")
    game.refresh_from_db()
    assert game.saved_game == saved


def test_saving_twice_gives_the_same_game(alice: User) -> None:
    game = services.resign(services.play_move(start(alice), move_uci="e2e4"))

    first = services.save_to_games(game)
    game.saved_game = None  # as if the link were lost: the game itself is still known
    second = services.save_to_games(game)

    assert first == second
    assert Game.objects.filter(user=alice).count() == 1


def test_a_timed_game_keeps_its_time_control(alice: User) -> None:
    game = services.resign(start(alice, clock_base_ms=600_000, clock_increment_ms=5_000))

    assert '[TimeControl "600+5"]' in services.save_to_games(game).pgn
