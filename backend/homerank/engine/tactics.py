"""Finding puzzles in analysed games: positions where one move clearly wins.

Two steps. find_candidates looks at a game's stored analysis for positions where the user
missed a chance, or where the opponent's blunder gave them one. solve then asks the engine
whether exactly one move wins there, and follows the line while it stays forced; positions
where several moves win make poor puzzles and are dropped.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import chess
import chess.engine

from homerank.engine.evaluation import win_percent

# How many percentage points of winning chances count as a big swing (a missed chance, or an
# opponent's blunder), and how good a position must be for the user to be worth a puzzle.
MIN_SWING = 20.0
CLEAR_ADVANTAGE = 66.0
# How much better the best move must be than the second best, in percentage points.
MIN_GAP = 25.0
# Winning chances at which a position is won anyway: if the second best move keeps them, the
# position needs no particular move, and is no puzzle.
ALREADY_WON = 95.0
# The engine compares the best two moves of each position (multipv).
CANDIDATE_MOVES = 2
# The longest solution, in half-moves (the user's moves and the replies between them).
MAX_PLIES = 9

PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
MATERIAL_GAIN = 2  # pawns won by the end of the solution for the theme "material"


class PuzzleKind(StrEnum):
    MISSED = "missed"  # the user's own move threw a chance away
    FOUND = "found"  # the opponent blundered, and the user punished it
    OPPONENT_BLUNDER = "opponent_blunder"  # the opponent blundered, and the user missed it


@dataclass(frozen=True)
class Candidate:
    ply: int  # the position, before the user's move: 0 is the starting position
    kind: PuzzleKind
    win_swing: float  # the percentage points the user lost, or the opponent gave away


def find_candidates(
    wins: Sequence[float],
    played: Sequence[str],
    best: Sequence[str],
    *,
    user_white: bool,
    white_first: bool = True,
) -> list[Candidate]:
    """Positions worth a puzzle, from a game's analysis: White's winning chances in every
    position (the starting position first), the moves played and the engine's best moves
    (UCI, one per position before a move)."""
    candidates = []
    for ply in range(len(played)):
        white_to_move = (ply % 2 == 0) == white_first
        if white_to_move != user_white or ply + 1 >= len(wins):
            continue

        def mine(index: int) -> float:
            return wins[index] if user_white else 100 - wins[index]

        if mine(ply) < CLEAR_ADVANTAGE:
            continue
        given = mine(ply) - mine(ply - 1) if ply > 0 else 0.0
        lost = mine(ply) - mine(ply + 1)
        if given >= MIN_SWING:
            found = played[ply] == best[ply]
            kind = PuzzleKind.FOUND if found else PuzzleKind.OPPONENT_BLUNDER
            candidates.append(Candidate(ply, kind, given))
        elif lost >= MIN_SWING:
            candidates.append(Candidate(ply, PuzzleKind.MISSED, lost))
    return candidates


def solve(
    engine: chess.engine.SimpleEngine, board: chess.Board, limit: chess.engine.Limit
) -> list[str]:
    """The forced winning line from the position, in UCI, starting and ending with a move of
    the side to move; [] if no single move clearly wins there."""
    board = board.copy()
    solution: list[str] = []
    while len(solution) < MAX_PLIES and not board.is_game_over():
        infos = engine.analyse(board, limit, multipv=CANDIDATE_MOVES)
        if len(infos) < CANDIDATE_MOVES or not _unique(infos[0], infos[1], board.turn):
            break  # an only move is no decision, and several good moves are no puzzle
        pv = infos[0].get("pv", [])
        if not pv:
            break
        board.push(pv[0])
        solution.append(pv[0].uci())
        if board.is_game_over() or len(solution) + 1 >= MAX_PLIES:
            break
        reply = pv[1] if len(pv) > 1 else engine.play(board, limit).move
        if reply is None:
            break
        board.push(reply)
        solution.append(reply.uci())
    if len(solution) % 2 == 0 and solution:
        solution.pop()  # end with the solver's move, not the reply
    return solution


def _unique(best: chess.engine.InfoDict, second: chess.engine.InfoDict, turn: bool) -> bool:
    """Whether the best move clearly beats the second best, for the side to move."""
    first = best["score"].pov(turn)
    other = second["score"].pov(turn)
    if (first.mate() or 0) > 0:
        # Every mate counts as the largest score, so mates need their own rule: unique unless
        # the second best move also leaves a position that is won anyway (a mate included).
        return _win(other) < ALREADY_WON
    return _win(first) - _win(other) >= MIN_GAP


def _win(score: chess.engine.Score) -> float:
    """Winning chances of the side whose point of view the score is from."""
    return win_percent(score.score(), score.mate(), white_to_move=True)


def themes(board: chess.Board, solution: Sequence[str]) -> list[str]:
    """Simple themes of a puzzle: "mate" and "mateInN" if the solution mates (as on Lichess, so
    that all mates can be chosen at once), "material" if it wins at least MATERIAL_GAIN pawns.
    More can be added later."""
    solver = board.turn
    after = board.copy()
    for uci in solution:
        after.push_uci(uci)
    found = []
    if after.is_checkmate():
        found += ["mate", f"mateIn{(len(solution) + 1) // 2}"]
    elif _material(after, solver) - _material(board, solver) >= MATERIAL_GAIN:
        found.append("material")
    return found


def _material(board: chess.Board, side: bool) -> int:
    """The side's material minus the other side's, in pawns."""
    return sum(
        value * (len(board.pieces(piece, side)) - len(board.pieces(piece, not side)))
        for piece, value in PIECE_VALUES.items()
    )
