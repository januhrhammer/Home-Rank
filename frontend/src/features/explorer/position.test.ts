import { describe, expect, test } from "vitest";

import { EMPTY_BOARD, fullFen, isLegalPosition, putPiece, readFen, START_BOARD } from "./position";

describe("setting up a position", () => {
  test("pieces are put on and taken off squares", () => {
    const withKing = putPiece(EMPTY_BOARD, "e1", { color: "white", role: "king" });
    expect(withKing).toBe("8/8/8/8/8/8/8/4K3");

    expect(putPiece(withKing, "e1", null)).toBe(EMPTY_BOARD);
  });

  test("castling is allowed where king and rook stand on their squares", () => {
    expect(fullFen(START_BOARD, "white")).toBe(`${START_BOARD} w KQkq - 0 1`);
    const noRookH1 = putPiece(START_BOARD, "h1", null);
    expect(fullFen(noRookH1, "black")).toBe(`${noRookH1} b Qkq - 0 1`);
    expect(fullFen("4k3/8/8/8/8/8/8/4K3", "white")).toBe("4k3/8/8/8/8/8/8/4K3 w - - 0 1");
  });

  test("illegal positions are recognised", () => {
    expect(isLegalPosition(fullFen(START_BOARD, "white"))).toBe(true);
    expect(isLegalPosition(fullFen(EMPTY_BOARD, "white"))).toBe(false); // no kings
    expect(isLegalPosition("nonsense")).toBe(false);
  });

  test("a typed FEN gives its board and side to move", () => {
    expect(readFen(` ${START_BOARD} b KQkq - 0 1 `)).toEqual({ board: START_BOARD, turn: "black" });
    expect(readFen("nonsense")).toBeNull();
  });
});
