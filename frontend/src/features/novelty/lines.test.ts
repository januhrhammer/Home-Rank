import { expect, test } from "vitest";

import { lineText, pawns, percent, tryMoves, ucisOf } from "./lines";

const MORRA = "r1bqk2r/pp2bppp/2np1n2/4p3/2B1P3/2N2N2/PP2QPPP/R1BR2K1 w kq - 0 10";

test("a try is written with its line, numbered from where it starts", () => {
  expect(lineText(tryMoves(MORRA, [], "b2b4"))).toBe("10.b4");
  expect(lineText(tryMoves(MORRA, ["c1e3", "e8g8"], "a1c1"))).toBe("10.Be3 O-O 11.Rac1");
  // A line starting with Black's move gets its number with an ellipsis.
  expect(lineText(tryMoves(MORRA, ["c1e3"], "e8g8"))).toBe("10.Be3 O-O");
  expect(lineText(tryMoves(MORRA, ["c1e3"], "e8g8").slice(1))).toBe("10…O-O");
});

test("evaluations and chances are written as players read them", () => {
  expect([pawns(35), pawns(-120), pawns(0)]).toEqual(["+0.35", "−1.20", "0.00"]);
  expect(percent(0.643)).toBe("64 %");
});

test("moves in SAN become UCI, promotions and castling included", () => {
  const start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
  expect(ucisOf(start, ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "O-O"])).toEqual([
    "e2e4",
    "e7e5",
    "g1f3",
    "b8c6",
    "f1c4",
    "g8f6",
    "e1g1",
  ]);
  expect(ucisOf("8/P6k/8/8/8/8/8/K7 w - - 0 1", ["a8=Q"])).toEqual(["a7a8q"]);
  expect(ucisOf(start, ["e5"])).toEqual([]);
});
