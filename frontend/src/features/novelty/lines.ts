/**
 * Moves of a novelty search as a reader sees them: numbered SAN from the search's start.
 * Pure functions, tested on their own.
 */
import { Chess } from "chessops/chess";
import { parseFen } from "chessops/fen";
import { parseSan } from "chessops/san";
import type { Move } from "chessops/types";
import { makeUci } from "chessops/util";

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

/** Moves written in SAN, from a position, as UCI; [] if one of them can't be played. */
export function ucisOf(startFen: string, sans: string[]): string[] {
  const position = Chess.fromSetup(parseFen(startFen).unwrap()).unwrap();
  const ucis = [];
  for (const san of sans) {
    const move = parseSan(position, san);
    if (move === undefined) {
      return [];
    }
    ucis.push(standardUci(position, move));
    position.play(move);
  }
  return ucis;
}

/** UCI as engines and the server write it. chessops writes castling as the king moving onto
 * its own rook (e1h1); UCI has the king's own square (e1g1). */
function standardUci(position: Chess, move: Move): string {
  const uci = makeUci(move);
  const piece = "from" in move ? position.board.get(move.from) : undefined;
  const target = "to" in move ? position.board.get(move.to) : undefined;
  if (piece?.role !== "king" || target?.role !== "rook" || target.color !== piece.color) {
    return uci;
  }
  const kingside = uci.charCodeAt(2) > uci.charCodeAt(0);
  return `${uci.slice(0, 2)}${kingside ? "g" : "c"}${uci[3] ?? ""}`;
}
