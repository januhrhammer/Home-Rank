"""Playing positions out against a bot (spec M8, ADR 0017).

A game is its starting position and its moves; the board is rebuilt from them for every
request. The user moves, and the bot answers in the same request, at once (maintainer's
choice): Maia in milliseconds, Stockfish in a fraction of a second. With a clock, each side's
time is its base time, plus the increment for each of its moves, minus the time its moves
took; the side to move also loses the time since turn_started_at.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus

import chess
import chess.pgn
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from homerank.accounts.models import User
from homerank.chesslib.pgn import PgnGame
from homerank.chesslib.players import Side
from homerank.core.errors import DomainError
from homerank.engine.bots import STOCKFISH_MAX_ELO, STOCKFISH_MIN_ELO, Bot, MaiaBot, StockfishBot
from homerank.engine.maia import load
from homerank.games.models import Game
from homerank.games.services import new_game, store_games
from homerank.play.models import BotGame, Opponent, Status, Termination

# The ratings offered (ADR 0017): Maia's are Lichess ratings, Stockfish's its own engine scale.
ELO_RANGES = {
    Opponent.MAIA: (800, 2400),
    Opponent.STOCKFISH: (STOCKFISH_MIN_ELO, STOCKFISH_MAX_ELO),
}
MAX_CLOCK_MS = 3 * 60 * 60 * 1000  # a base time of at most 3 hours
MAX_INCREMENT_MS = 60 * 1000  # and at most a minute per move
TAKE_BACK = 2  # moves taken back at once: the user's and the bot's answer

# How python-chess names the ends of a game, in our terms. The 75-move rule and fivefold
# repetition end a game even without a claim; here they count as their claimable versions.
TERMINATIONS = {
    chess.Termination.CHECKMATE: Termination.CHECKMATE,
    chess.Termination.STALEMATE: Termination.STALEMATE,
    chess.Termination.INSUFFICIENT_MATERIAL: Termination.INSUFFICIENT_MATERIAL,
    chess.Termination.THREEFOLD_REPETITION: Termination.THREEFOLD_REPETITION,
    chess.Termination.FIVEFOLD_REPETITION: Termination.THREEFOLD_REPETITION,
    chess.Termination.FIFTY_MOVES: Termination.FIFTY_MOVES,
    chess.Termination.SEVENTYFIVE_MOVES: Termination.FIFTY_MOVES,
}


class InvalidPositionError(DomainError):
    detail = "This isn't a valid position to play from."


class EloOutOfRangeError(DomainError):
    detail = "This opponent doesn't play at that rating."


class InvalidClockError(DomainError):
    detail = (
        f"A clock needs a base time of up to {MAX_CLOCK_MS // 3_600_000} hours and an "
        f"increment of up to {MAX_INCREMENT_MS // 1000} seconds."
    )


class GameFinishedError(DomainError):
    status = HTTPStatus.CONFLICT
    detail = "This game is over."


class NotYourTurnError(DomainError):
    status = HTTPStatus.CONFLICT
    detail = "It's not your move."


class IllegalMoveError(DomainError):
    detail = "This move isn't legal in this position."


class NoTakeBackError(DomainError):
    status = HTTPStatus.CONFLICT
    detail = "There is no move of yours to take back, or the game has a clock."


# ---------------------------------------------------------------- the board and the clock


def board_of(game: BotGame) -> chess.Board:
    """The game's position now: its starting position with its moves played."""
    board = chess.Board(game.start_fen)
    for move in game.moves:
        board.push_uci(move)
    return board


def _users_turn(game: BotGame, board: chess.Board) -> bool:
    return board.turn == (game.user_color == Side.WHITE)


@dataclass(frozen=True)
class Clock:
    """Each side's time left, in milliseconds, at a moment."""

    white_ms: int
    black_ms: int


def clock_at(game: BotGame, now: datetime) -> Clock | None:
    """The clock at `now`, or None for an untimed game. Time left can be negative: the side
    to move has run out of time, which play_move and settle_clock turn into a loss."""
    if game.clock_base_ms is None or game.clock_increment_ms is None:
        return None
    first = chess.Board(game.start_fen).turn
    left = {chess.WHITE: game.clock_base_ms, chess.BLACK: game.clock_base_ms}
    for ply, took in enumerate(game.move_ms):
        side = first if ply % 2 == 0 else not first
        left[side] += game.clock_increment_ms - took
    if game.status == Status.PLAYING and game.turn_started_at is not None:
        to_move = first if len(game.moves) % 2 == 0 else not first
        left[to_move] -= _ms_between(game.turn_started_at, now)
    return Clock(white_ms=left[chess.WHITE], black_ms=left[chess.BLACK])


def _ms_between(start: datetime, end: datetime) -> int:
    return max(0, round((end - start).total_seconds() * 1000))


def _finish(game: BotGame, *, result: str, termination: str, now: datetime) -> None:
    game.status = Status.FINISHED
    game.result = result
    game.termination = termination
    game.finished_at = now
    game.turn_started_at = None


def _finish_if_over(game: BotGame, board: chess.Board, now: datetime) -> None:
    """End the game if the position ends it: mate, stalemate, or a draw by the rules (claimed
    at once, as Lichess does)."""
    outcome = board.outcome(claim_draw=True)
    if outcome is not None:
        _finish(
            game, result=outcome.result(), termination=TERMINATIONS[outcome.termination], now=now
        )


def _flag(game: BotGame, board: chess.Board, *, loser: chess.Color, now: datetime) -> None:
    """`loser` ran out of time: they lose, unless the other side couldn't mate at all."""
    if board.has_insufficient_material(not loser):
        result = "1/2-1/2"
    else:
        result = "0-1" if loser == chess.WHITE else "1-0"
    _finish(game, result=result, termination=Termination.TIMEOUT, now=now)


def settle_clock(game: BotGame, *, now: datetime) -> BotGame:
    """End a game whose side to move has run out of time; the game is saved if it changed.
    Without this, a user who stops playing would keep a game "being played" forever."""
    clock = clock_at(game, now)
    if game.status != Status.PLAYING or clock is None:
        return game
    board = board_of(game)
    left = clock.white_ms if board.turn == chess.WHITE else clock.black_ms
    if left < 0:
        _flag(game, board, loser=board.turn, now=now)
        game.save()
    return game


# ---------------------------------------------------------------- playing


def _bot(game: BotGame) -> Bot:
    if game.opponent == Opponent.MAIA:
        # Maia is asked for a move of a player of this rating facing an equal opponent.
        model = load(settings.MAIA_PATH)
        return MaiaBot(model, elo=game.opponent_elo, opponent_elo=game.opponent_elo)
    return StockfishBot(settings.STOCKFISH_PATH, elo=game.opponent_elo)


def _bot_moves(game: BotGame, board: chess.Board, now: datetime) -> None:
    """The bot's move at `now`, if it is the bot's turn and the game goes on. The time it
    took to compute counts against its clock."""
    if game.status != Status.PLAYING or _users_turn(game, board):
        return
    started = time.monotonic()
    move = _bot(game).move(board)
    took = round((time.monotonic() - started) * 1000)
    board.push(move)
    game.moves.append(move.uci())
    game.move_ms.append(took)
    game.turn_started_at = now + timedelta(milliseconds=took)
    _finish_if_over(game, board, game.turn_started_at)


@dataclass(frozen=True)
class Setup:
    """How a new game is to be played."""

    start_fen: str
    user_color: Side
    opponent: Opponent
    opponent_elo: int
    clock_base_ms: int | None = None  # None: untimed
    clock_increment_ms: int | None = None
    start_label: str = ""  # e.g. "Sicilian and more, after 1. e4 c5"


def start_game(*, user: User, setup: Setup) -> BotGame:
    """A new game. If the bot is to move in the starting position, it moves at once."""
    try:
        board = chess.Board(setup.start_fen)
    except ValueError as error:
        raise InvalidPositionError from error
    if not board.is_valid() or board.is_game_over(claim_draw=True):
        raise InvalidPositionError
    low, high = ELO_RANGES[setup.opponent]
    if not low <= setup.opponent_elo <= high:
        raise EloOutOfRangeError
    base, increment = setup.clock_base_ms, setup.clock_increment_ms
    if (base is None) != (increment is None):
        raise InvalidClockError
    if (
        base is not None
        and increment is not None
        and not (0 < base <= MAX_CLOCK_MS and 0 <= increment <= MAX_INCREMENT_MS)
    ):
        raise InvalidClockError

    now = timezone.now()
    game = BotGame(
        user=user,
        start_fen=board.fen(),
        start_label=setup.start_label,
        user_color=setup.user_color,
        opponent=setup.opponent,
        opponent_elo=setup.opponent_elo,
        clock_base_ms=base,
        clock_increment_ms=increment,
        turn_started_at=now,
    )
    _bot_moves(game, board, now)
    game.save()
    return game


def play_move(game: BotGame, *, move_uci: str, now: datetime | None = None) -> BotGame:
    """The user's move, and the bot's answer. With a clock, a move made after the user's time
    ran out isn't played: the game is lost on time."""
    with transaction.atomic():
        # One move at a time per game, even if the user clicks twice.
        game = BotGame.objects.select_for_update().get(pk=game.pk)
        now = now or timezone.now()
        if game.status != Status.PLAYING:
            raise GameFinishedError
        board = board_of(game)
        if not _users_turn(game, board):
            raise NotYourTurnError
        try:
            move = chess.Move.from_uci(move_uci)
        except chess.InvalidMoveError as error:
            raise IllegalMoveError from error
        if move not in board.legal_moves:
            raise IllegalMoveError

        clock = clock_at(game, now)
        if clock is not None and (clock.white_ms if board.turn else clock.black_ms) < 0:
            _flag(game, board, loser=board.turn, now=now)
        else:
            took = 0 if game.turn_started_at is None else _ms_between(game.turn_started_at, now)
            board.push(move)
            game.moves.append(move.uci())
            game.move_ms.append(took)
            game.turn_started_at = now
            _finish_if_over(game, board, now)
            _bot_moves(game, board, now)
        game.save()
    return game


def take_back(game: BotGame) -> BotGame:
    """Take back the user's last move, and the bot's answer to it. Only in untimed games that
    are still being played."""
    with transaction.atomic():
        game = BotGame.objects.select_for_update().get(pk=game.pk)
        if game.status != Status.PLAYING or game.clock_base_ms is not None:
            raise NoTakeBackError
        # While a game goes on, the bot has always answered: undo its answer and the user's
        # move before it, back to the user's turn.
        if len(game.moves) < TAKE_BACK or not _users_turn(game, board_of(game)):
            raise NoTakeBackError
        del game.moves[-TAKE_BACK:]
        del game.move_ms[-TAKE_BACK:]
        game.turn_started_at = timezone.now()
        game.save()
    return game


def resign(game: BotGame) -> BotGame:
    with transaction.atomic():
        game = BotGame.objects.select_for_update().get(pk=game.pk)
        if game.status != Status.PLAYING:
            raise GameFinishedError
        result = "0-1" if game.user_color == Side.WHITE else "1-0"
        _finish(game, result=result, termination=Termination.RESIGNATION, now=timezone.now())
        game.save()
    return game


# ---------------------------------------------------------------- into the user's games


def opponent_name(game: BotGame) -> str:
    """The bot as a player's name: "Maia 1500", "Stockfish 2000"."""
    return f"{Opponent(game.opponent).label} {game.opponent_elo}"


def save_to_games(game: BotGame) -> Game:
    """Store a game as one of the user's games, like an imported one (analysed and searchable
    as usual), and link it. Saving it again returns the same game."""
    if game.saved_game is not None:
        return game.saved_game
    user = game.user
    pgn_game = _pgn(game)
    pgn = str(pgn_game)
    new = new_game(user, PgnGame(line=1, pgn=pgn, game=pgn_game))
    store_games(user, [new])  # skips it if the user already has this game
    saved = Game.objects.get(user=user, dedup_hash=new.game.dedup_hash)
    game.saved_game = saved
    game.save(update_fields=["saved_game"])
    return saved


def _pgn(game: BotGame) -> chess.pgn.Game:
    # The moves from the game's start; a start other than the usual one gets SetUp and FEN.
    pgn_game = chess.pgn.Game.from_board(board_of(game))
    # The user under the first name they play under, so Home-Rank finds their side.
    user_name = game.user.player_names[0] if game.user.player_names else game.user.username
    bot = opponent_name(game)
    white, black = (user_name, bot) if game.user_color == Side.WHITE else (bot, user_name)
    pgn_game.headers.update(
        {
            "Event": f"Practice against {bot}"
            + (f": {game.start_label}" if game.start_label else ""),
            "Site": "Home-Rank",
            "Date": timezone.localtime(game.created_at).strftime("%Y.%m.%d"),
            "White": white,
            "Black": black,
            "Result": game.result or "*",
        }
    )
    if game.clock_base_ms is not None and game.clock_increment_ms is not None:
        base, increment = game.clock_base_ms // 1000, game.clock_increment_ms // 1000
        pgn_game.headers["TimeControl"] = f"{base}+{increment}"
    return pgn_game
