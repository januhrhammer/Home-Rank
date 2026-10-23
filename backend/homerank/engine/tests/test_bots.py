import random

import chess
import chess.engine
import pytest

from homerank.engine.bots import STOCKFISH_MAX_ELO, STOCKFISH_MIN_ELO, MaiaBot, StockfishBot
from homerank.engine.maia import GameOverError, load
from homerank.engine.uci import open_engine

# After 1. e4 e5 2. Nf3 Nc6: both bots must answer for White.
ITALIAN = ["e2e4", "e7e5", "g1f3", "b8c6"]


def board_after(moves: list[str]) -> chess.Board:
    board = chess.Board()
    for move in moves:
        board.push_uci(move)
    return board


@pytest.mark.maia
def test_maia_plays_a_legal_move(maia_model: str) -> None:
    bot = MaiaBot(load(maia_model), elo=1500, opponent_elo=1500, rng=random.Random(3))
    board = board_after(ITALIAN)

    assert bot.move(board) in board.legal_moves


@pytest.mark.maia
def test_maia_plays_a_whole_game_against_itself(maia_model: str) -> None:
    # Positions far from any opening, with promotions and long histories, must all work.
    white = MaiaBot(load(maia_model), elo=1100, opponent_elo=1100, rng=random.Random(4))
    black = MaiaBot(load(maia_model), elo=1100, opponent_elo=1100, rng=random.Random(5))
    board = chess.Board()

    while not board.is_game_over(claim_draw=True):
        board.push((white if board.turn == chess.WHITE else black).move(board))

    assert board.outcome(claim_draw=True) is not None


@pytest.mark.engine
def test_stockfish_plays_a_legal_move_at_its_lowest_strength(stockfish: str) -> None:
    bot = StockfishBot(stockfish, elo=STOCKFISH_MIN_ELO, seconds=0.05)
    board = board_after(ITALIAN)

    assert bot.move(board) in board.legal_moves


@pytest.mark.engine
def test_the_strength_range_is_stockfishs_own(stockfish: str) -> None:
    with open_engine(stockfish) as engine:
        option = engine.options["UCI_Elo"]

    assert (option.min, option.max) == (STOCKFISH_MIN_ELO, STOCKFISH_MAX_ELO)


@pytest.mark.engine
def test_stockfish_has_no_move_when_the_game_is_over(stockfish: str) -> None:
    mated = board_after(["f2f3", "e7e5", "g2g4", "d8h4"])

    with pytest.raises(GameOverError):
        StockfishBot(stockfish, elo=STOCKFISH_MIN_ELO, seconds=0.05).move(mated)
