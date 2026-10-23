/**
 * Solving a puzzle, move by move: which moves count, the opponent's replies, and how it ends.
 * Pure functions over chessops positions, so the rules can be tested without a board.
 */
import type { SquareName } from "chessops";
import { Chess } from "chessops/chess";
import { chessgroundDests } from "chessops/compat";
import { makeFen, parseFen } from "chessops/fen";
import { parseSan } from "chessops/san";
import { makeSquare, makeUci, parseSquare, parseUci } from "chessops/util";

export type Status = "playing" | "solved" | "shown";

export interface Progress {
  /** The position on the board. */
  fen: string;
  /** How many moves of the solution have been played, the replies included. */
  step: number;
  /** The squares of the last move, to highlight. */
  lastMove: SquareName[];
  /** Whether a wrong move was tried: then the puzzle counts as failed. */
  wrong: boolean;
  status: Status;
}

/** The squares a move in UCI went from and to: "e2e4" → ["e2", "e4"]. */
export function squaresOf(uci: string): SquareName[] {
  return uci.length >= 4 ? [uci.slice(0, 2) as SquareName, uci.slice(2, 4) as SquareName] : [];
}

export function begin(fen: string, lastMoveUci: string): Progress {
  return { fen, step: 0, lastMove: squaresOf(lastMoveUci), wrong: false, status: "playing" };
}

function position(fen: string): Chess {
  return Chess.fromSetup(parseFen(fen).unwrap()).unwrap();
}

/** The colour to move in a position, as chessground names it. */
export function turnOf(fen: string): "white" | "black" {
  return position(fen).turn;
}

/** Where each piece of the side to move may go, for the board. */
export function legalDests(fen: string): Map<SquareName, SquareName[]> {
  return chessgroundDests(position(fen));
}

/**
 * A move dragged on the board, from and to, as UCI. A pawn reaching the last rank becomes the
 * piece the solution asks for if it moves as the solution does, otherwise a queen.
 */
export function boardMove(fen: string, from: string, to: string, expected: string): string {
  const base = `${from}${to}`;
  if (expected.startsWith(base)) {
    return expected;
  }
  const square = parseSquare(from);
  const piece = square === undefined ? undefined : position(fen).board.get(square);
  const lastRank = to.endsWith("8") || to.endsWith("1");
  return piece?.role === "pawn" && lastRank ? `${base}q` : base;
}

/** A typed move, in SAN ("Nf3", "exd8=Q") or UCI ("g1f3"), as UCI; null if not legal here. */
export function typedMove(fen: string, text: string): string | null {
  const pos = position(fen);
  const trimmed = text.trim();
  const move = parseSan(pos, trimmed) ?? parseUci(trimmed.toLowerCase());
  return move !== undefined && pos.isLegal(move) ? makeUci(move) : null;
}

function play(fen: string, uci: string): Chess {
  const pos = position(fen);
  const move = parseUci(uci);
  if (move === undefined || !pos.isLegal(move)) {
    throw new Error(`illegal move ${uci} in ${fen}`);
  }
  pos.play(move);
  return pos;
}

/**
 * The user's move: right if it is the solution's move, or if it mates (another mate is as
 * good). A right move is played; a wrong one isn't, but marks the puzzle as failed.
 */
export function tryMove(progress: Progress, solution: string[], uci: string): Progress {
  const expected = solution[progress.step];
  if (progress.status !== "playing" || expected === undefined) {
    return progress;
  }
  const after = play(progress.fen, uci);
  if (uci !== expected && !after.isCheckmate()) {
    return { ...progress, wrong: true };
  }
  const step = progress.step + 1;
  return {
    ...progress,
    fen: makeFen(after.toSetup()),
    step,
    lastMove: squaresOf(uci),
    // A mate ends the puzzle even if the solution goes on (an earlier mate was found).
    status: step >= solution.length || after.isCheckmate() ? "solved" : "playing",
  };
}

/** Whether the opponent's reply is due: the user's move was right and the solution goes on. */
export function replyDue(progress: Progress, solution: string[]): boolean {
  return (
    progress.status === "playing" && progress.step % 2 === 1 && progress.step < solution.length
  );
}

/** Plays the opponent's reply from the solution. */
export function reply(progress: Progress, solution: string[]): Progress {
  const uci = solution[progress.step];
  if (uci === undefined) {
    return progress;
  }
  const after = play(progress.fen, uci);
  return {
    ...progress,
    fen: makeFen(after.toSetup()),
    step: progress.step + 1,
    lastMove: squaresOf(uci),
  };
}

/** Plays out the rest of the solution, as when the user gives up: the puzzle is failed. */
export function showSolution(progress: Progress, solution: string[]): Progress {
  let fen = progress.fen;
  let lastMove = progress.lastMove;
  for (const uci of solution.slice(progress.step)) {
    fen = makeFen(play(fen, uci).toSetup());
    lastMove = squaresOf(uci);
  }
  return { fen, step: solution.length, lastMove, wrong: true, status: "shown" };
}

/** How many moves of the user's the solution has. */
export function solverMoves(solution: string[]): number {
  return Math.ceil(solution.length / 2);
}

export { makeSquare };
