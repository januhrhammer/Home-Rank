/**
 * Moves of a novelty search as a reader sees them: numbered SAN from the search's start.
 * Pure functions, tested on their own.
 */
import { type PlayedMove, playedMoves } from "../play";

/** Moves written as a line from wherever the first one is played: "10.b4 Bg4 11.O-O". */
export function lineText(
  moves: PlayedMove[],
  format: (san: string) => string = (san) => san,
): string {
  return moves
    .map((move, index) => {
      const number = move.white
        ? `${String(move.number)}.`
        : index === 0
          ? `${String(move.number)}…`
          : "";
      return `${number}${format(move.san)}`;
    })
    .join(" ");
}

/** A try's moves from the search's start: the line to it, then the try itself. */
export function tryMoves(startFen: string, line: string[], uci: string): PlayedMove[] {
  return playedMoves(startFen, [...line, uci]);
}

/** A centipawn evaluation as players write it: +0.35, −1.20, 0.00. */
export function pawns(cp: number): string {
  const text = (Math.abs(cp) / 100).toFixed(2);
  return cp > 0 ? `+${text}` : cp < 0 ? `−${text}` : text;
}

/** A probability as a whole percentage: 0.643 → "64 %". */
export function percent(share: number): string {
  return `${String(Math.round(share * 100))} %`;
}
