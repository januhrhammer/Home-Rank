/**
 * What the play page shows, worked out from a game: its moves in SAN, the clock as text, and
 * how the game ended for the user. Pure functions, tested without a board.
 */
import { Chess } from "chessops/chess";
import { makeFen, parseFen } from "chessops/fen";
import { makeSanAndPlay } from "chessops/san";
import { parseUci } from "chessops/util";

export interface PlayedMove {
  /** The move's number, as written before White's move: 1. e4 */
  number: number;
  white: boolean;
  san: string;
  uci: string;
  /** The position after the move. */
  fen: string;
}

/** The game's moves from its start, in SAN. */
export function playedMoves(startFen: string, moves: string[]): PlayedMove[] {
  const position = Chess.fromSetup(parseFen(startFen).unwrap()).unwrap();
  return moves.map((uci) => {
    const move = parseUci(uci);
    if (move === undefined) {
      throw new Error(`not a move: ${uci}`);
    }
    const white = position.turn === "white";
    const number = position.fullmoves;
    const san = makeSanAndPlay(position, move);
    return { number, white, san, uci, fen: makeFen(position.toSetup()) };
  });
}

/** Time left as a clock shows it: 4:05, 0:09.3 in the last ten seconds, 1:02:00 from an
 * hour on; never below 0:00. */
export function clockText(ms: number): string {
  const left = Math.max(0, ms);
  if (left < 10_000) {
    return `0:0${(Math.floor(left / 100) / 10).toFixed(1)}`;
  }
  const seconds = Math.floor(left / 1000);
  const [h, m, s] = [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60];
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${String(h)}:${pad(m)}:${pad(s)}` : `${String(m)}:${pad(s)}`;
}

export type Outcome = "won" | "lost" | "drawn";

/** How a finished game went for the user; null while it goes on. */
export function outcomeFor(result: string, userColor: "white" | "black"): Outcome | null {
  if (result === "1/2-1/2") {
    return "drawn";
  }
  if (result === "1-0" || result === "0-1") {
    return (result === "1-0") === (userColor === "white") ? "won" : "lost";
  }
  return null;
}

/** The pieces one side has more of than the other, and by how many points it is ahead. */
export interface Ahead {
  /** Piece letters, the most valuable first: ["N", "P", "P"]. */
  pieces: string[];
  /** Points ahead (pawn 1, knight and bishop 3, rook 5, queen 9); 0 if not ahead. */
  advantage: number;
}

const VALUES: [string, number][] = [
  ["Q", 9],
  ["R", 5],
  ["B", 3],
  ["N", 3],
  ["P", 1],
];

/** What each side is up in material in the position, as next to the players on Lichess. */
export function material(fen: string): { white: Ahead; black: Ahead } {
  const board = fen.split(" ")[0] ?? "";
  const count = (letter: string) => board.split(letter).length - 1;
  const white: Ahead = { pieces: [], advantage: 0 };
  const black: Ahead = { pieces: [], advantage: 0 };
  let score = 0;
  for (const [letter, value] of VALUES) {
    const difference = count(letter) - count(letter.toLowerCase());
    const ahead = difference > 0 ? white : black;
    for (let i = 0; i < Math.abs(difference); i++) {
      ahead.pieces.push(letter);
    }
    score += difference * value;
  }
  white.advantage = Math.max(0, score);
  black.advantage = Math.max(0, -score);
  return { white, black };
}
