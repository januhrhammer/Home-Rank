import { expect, test } from "vitest";

import { clockText, material, outcomeFor, playedMoves } from "./moves";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

test("moves are numbered and written in SAN, from any start", () => {
  expect(
    playedMoves(START, ["e2e4", "c7c5", "g1f3"]).map((m) => [m.number, m.white, m.san]),
  ).toEqual([
    [1, true, "e4"],
    [1, false, "c5"],
    [2, true, "Nf3"],
  ]);
  // Black to move first, at move 12.
  const fromBlack = playedMoves("4k3/8/8/8/8/8/4P3/4K3 b - - 0 12", ["e8d7", "e2e4"]);
  expect(fromBlack.map((m) => [m.number, m.white, m.san])).toEqual([
    [12, false, "Kd7"],
    [13, true, "e4"],
  ]);
  expect(fromBlack[1]?.fen).toBe("8/3k4/8/8/4P3/8/8/4K3 b - - 0 13");
});

test("the clock shows minutes, tenths at the end, hours when needed, never less than zero", () => {
  expect(clockText(245_000)).toBe("4:05");
  expect(clockText(9_340)).toBe("0:09.3");
  expect(clockText(3_720_000)).toBe("1:02:00");
  expect(clockText(-500)).toBe("0:00.0");
});

test("the result from the user's side", () => {
  expect(outcomeFor("1-0", "white")).toBe("won");
  expect(outcomeFor("1-0", "black")).toBe("lost");
  expect(outcomeFor("0-1", "black")).toBe("won");
  expect(outcomeFor("1/2-1/2", "white")).toBe("drawn");
  expect(outcomeFor("", "white")).toBeNull();
});

test("material: the pieces each side is up, and by how much", () => {
  expect(material(START)).toEqual({
    white: { pieces: [], advantage: 0 },
    black: { pieces: [], advantage: 0 },
  });
  // Black has no knights and five pawns, White one bishop: White is up N P P P (6), Black up
  // B (3), so White is 3 ahead.
  const fen = "r1bqkb1r/pp3ppp/8/8/8/8/PPPPPPPP/R1BQK1NR w KQkq - 0 10";
  expect(material(fen)).toEqual({
    white: { pieces: ["N", "P", "P", "P"], advantage: 3 },
    black: { pieces: ["B"], advantage: 0 },
  });
  // A promoted queen counts as a queen.
  expect(material("4k3/8/8/8/8/8/8/Q3K3 w - - 0 60").white).toEqual({
    pieces: ["Q"],
    advantage: 9,
  });
});
