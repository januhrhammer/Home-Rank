import { expect, test } from "vitest";

import { arrowsOf, parseInfo, scoreText } from "./uci";

test("an info line with a line of moves is read, scored from White's side", () => {
  const line =
    "info depth 18 seldepth 24 multipv 2 score cp -35 nodes 812345 nps 1500000 hashfull 120 tbhits 0 time 540 pv e7e5 g1f3 b8c6";

  expect(parseInfo(line, true)).toEqual({
    rank: 2,
    depth: 18,
    score: { cp: -35 },
    moves: ["e7e5", "g1f3", "b8c6"],
  });
  // The same words with Black to move: Stockfish's -35 is good for White.
  expect(parseInfo(line, false)?.score).toEqual({ cp: 35 });
});

test("mates keep their sign from White's side; a missing multipv means the best line", () => {
  expect(parseInfo("info depth 5 score mate 3 pv d1h5", true)).toMatchObject({
    rank: 1,
    score: { mate: 3 },
  });
  expect(parseInfo("info depth 5 score mate 2 pv d8h4", false)?.score).toEqual({ mate: -2 });
});

test("lines that aren't results are skipped", () => {
  expect(parseInfo("info string NNUE evaluation using nn-small.nnue", true)).toBeNull();
  expect(parseInfo("info depth 10 currmove e2e4 currmovenumber 1", true)).toBeNull();
  expect(parseInfo("info depth 12 score cp 20 lowerbound nodes 9 pv e2e4", true)).toBeNull();
  expect(parseInfo("bestmove e2e4 ponder e7e5", true)).toBeNull();
});

test("scores are written as people do", () => {
  expect(scoreText({ cp: 32 })).toBe("+0.32");
  expect(scoreText({ cp: -150 })).toBe("−1.50");
  expect(scoreText({ cp: 0 })).toBe("+0.00");
  expect(scoreText({ mate: 3 })).toBe("#3");
  expect(scoreText({ mate: -2 })).toBe("#−2");
});

test("each line's first move becomes an arrow, the best one marked", () => {
  const line = (rank: number, moves: string[]) => ({ rank, depth: 9, score: { cp: 0 }, moves });

  expect(arrowsOf([line(1, ["e7e8q", "a1a2"]), line(2, ["g1f3"]), line(3, [])])).toEqual([
    { from: "e7", to: "e8", best: true },
    { from: "g1", to: "f3", best: false },
  ]);
});
