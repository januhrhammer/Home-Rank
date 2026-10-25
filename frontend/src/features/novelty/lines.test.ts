import { expect, test } from "vitest";

import { lineText, pawns, percent, tryMoves } from "./lines";

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
