import type { SquareName } from "chessops";

/**
 * Reading what Stockfish says over UCI, the protocol of chess engines: its "info" lines carry
 * each line of moves it considers, with its depth and score. Pure functions, tested alone.
 */

/** A score from White's point of view: centipawns, or moves to mate (negative: Black mates). */
export type Score = { cp: number } | { mate: number };

export interface EngineLine {
  /** 1 for the best line, 2 for the second best, … */
  rank: number;
  depth: number;
  score: Score;
  /** The line's moves in UCI, from the position analysed. */
  moves: string[];
}

/**
 * One "info" line as an EngineLine, or null if it isn't one (e.g. "info string …", or an
 * info without a line of moves). Stockfish scores from the side to move's point of view;
 * `whiteToMove` turns that into White's.
 */
export function parseInfo(line: string, whiteToMove: boolean): EngineLine | null {
  const words = line.trim().split(/\s+/);
  if (words[0] !== "info" || !words.includes("pv") || words.includes("string")) {
    return null;
  }
  const after = (key: string) => {
    const index = words.indexOf(key);
    return index === -1 ? undefined : words[index + 1];
  };
  const depth = Number(after("depth"));
  const rank = Number(after("multipv") ?? "1");
  const scoreIndex = words.indexOf("score");
  const kind = words[scoreIndex + 1];
  const value = Number(words[scoreIndex + 2]);
  if (scoreIndex === -1 || Number.isNaN(depth) || Number.isNaN(value)) {
    return null;
  }
  // "lowerbound"/"upperbound" scores are a search's passing guesses, not results.
  if (words.includes("lowerbound") || words.includes("upperbound")) {
    return null;
  }
  const sign = whiteToMove ? 1 : -1;
  const score: Score = kind === "mate" ? { mate: sign * value } : { cp: sign * value };
  return { rank, depth, score, moves: words.slice(words.indexOf("pv") + 1) };
}

/** A score as people write it: +0.32, −1.50, #3 (White mates), #−2 (Black mates). */
export function scoreText(score: Score): string {
  if ("mate" in score) {
    return score.mate >= 0 ? `#${String(score.mate)}` : `#−${String(-score.mate)}`;
  }
  const pawns = (Math.abs(score.cp) / 100).toFixed(2);
  return score.cp >= 0 ? `+${pawns}` : `−${pawns}`;
}

/** Each line's first move as an arrow on the board; the best line's stands out. */
export function arrowsOf(
  lines: EngineLine[],
): { from: SquareName; to: SquareName; best: boolean }[] {
  return lines.flatMap((line) => {
    const move = line.moves[0];
    if (move === undefined) {
      return [];
    }
    // UCI moves start with two square names: "e2e4", "e7e8q".
    const from = move.slice(0, 2) as SquareName;
    const to = move.slice(2, 4) as SquareName;
    return [{ from, to, best: line.rank === 1 }];
  });
}
