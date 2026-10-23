/**
 * Where a game left the user's repertoire: the first position the repertoire covers in which
 * the move played isn't one of its moves. A pure function over the game's moves and the
 * repertoire's, tested on its own.
 */
import type { PlayedMove } from "./moves";

/** One move of one of the user's repertoires, with the repertoire it belongs to. */
export interface BookMove {
  repertoire: string;
  fromFen: string;
  moveUci: string;
  moveSan: string;
}

export interface Departure {
  /** The move that left the repertoire. */
  move: PlayedMove;
  /** Whether the user played it; else the bot did. */
  byUser: boolean;
  repertoire: string;
  /** What the repertoire has in that position (empty: no reply prepared). */
  expected: string[];
}

/** A position without the move counters, which repertoires and games may count differently. */
function positionKey(fen: string): string {
  return fen.split(" ").slice(0, 4).join(" ");
}

export function departure(
  startFen: string,
  moves: PlayedMove[],
  book: BookMove[],
  userColor: "white" | "black",
): Departure | null {
  const byPosition = new Map<string, BookMove[]>();
  for (const move of book) {
    const key = positionKey(move.fromFen);
    byPosition.set(key, [...(byPosition.get(key) ?? []), move]);
  }
  let fen = startFen;
  let repertoire: string | null = null;
  for (const move of moves) {
    const known = byPosition.get(positionKey(fen)) ?? [];
    if (known.length === 0) {
      // Not covered: if the game was in the repertoire before, the last move led out of it
      // already (and was reported), or the repertoire simply ends here.
      return null;
    }
    repertoire = known[0]?.repertoire ?? repertoire;
    if (!known.some((entry) => entry.moveUci === move.uci)) {
      return {
        move,
        byUser: move.white === (userColor === "white"),
        repertoire: repertoire ?? "",
        expected: known.map((entry) => entry.moveSan),
      };
    }
    fen = move.fen;
  }
  return null;
}
