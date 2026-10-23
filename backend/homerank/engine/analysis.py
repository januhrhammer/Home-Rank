"""Analysing a game with the engine: a score, best move and main line for every position."""

from collections.abc import Iterator
from dataclasses import dataclass

import chess
import chess.engine
import chess.pgn

from homerank.engine.evaluation import win_percent

# Moves of the engine's main line (PV) kept per position: enough to show the idea.
PV_LENGTH = 10


@dataclass(frozen=True)
class PositionAnalysis:
    """The engine's view of one position of a game's main line, from White's point of view."""

    ply: int  # 0 is the starting position, n the position after the n-th half-move
    depth: int  # 0 for finished positions (mate, stalemate, …), which need no engine
    score_cp: int | None  # None when there is a mate
    score_mate: int | None  # moves to mate, > 0 if White mates; 0: the side to move is mated
    win_percent: float  # White's winning chances, 0 to 100
    best_move_uci: str  # "" in finished positions
    pv: list[str]  # the engine's main line in UCI notation, best move first


def analyse_game(
    engine: chess.engine.SimpleEngine, game: chess.pgn.Game, limit: chess.engine.Limit
) -> Iterator[PositionAnalysis]:
    """Analyse every position of the game's main line, the starting position first.

    Positions are yielded one by one, so the caller can save them and report progress.
    """
    board = game.board()
    yield _analyse(engine, board, 0, limit)
    for ply, move in enumerate(game.mainline_moves(), start=1):
        board.push(move)
        yield _analyse(engine, board, ply, limit)


def _analyse(
    engine: chess.engine.SimpleEngine, board: chess.Board, ply: int, limit: chess.engine.Limit
) -> PositionAnalysis:
    white_to_move = board.turn == chess.WHITE
    if board.is_game_over(claim_draw=False):
        mate = 0 if board.is_checkmate() else None
        cp = None if board.is_checkmate() else 0  # stalemate, insufficient material, …
        return PositionAnalysis(
            ply=ply,
            depth=0,
            score_cp=cp,
            score_mate=mate,
            win_percent=win_percent(cp, mate, white_to_move=white_to_move),
            best_move_uci="",
            pv=[],
        )
    info = engine.analyse(board, limit)
    score = info["score"].white()
    cp, mate = score.score(), score.mate()
    pv = [move.uci() for move in info.get("pv", [])[:PV_LENGTH]]
    return PositionAnalysis(
        ply=ply,
        depth=info.get("depth", 0),
        score_cp=cp,
        score_mate=mate,
        win_percent=win_percent(cp, mate, white_to_move=white_to_move),
        best_move_uci=pv[0] if pv else "",
        pv=pv,
    )
