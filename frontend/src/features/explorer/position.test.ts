import { describe, expect, test } from "vitest";

import {
  asMove,
  EMPTY_BOARD,
  fullFen,
  isLegalPosition,
  playMove,
  putPiece,
  readFen,
  START_BOARD,
} from "./position";

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

describe("moving on the set-up board", () => {
  const start = fullFen(START_BOARD, "white");
  const afterE4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR";

  test("a legal move dragged passes the move to the other side", () => {
    expect(asMove(start, afterE4)).toEqual({ board: afterE4, turn: "black" });
  });

  test("castling dragged is a move too", () => {
    const fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1";
    expect(asMove(fen, "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R4RK1")?.turn).toBe("black");
  });

  test("a piece put where no move takes it stays a set-up change", () => {
    // The e-pawn to e5 in one go, or a black pawn moved while White is to move.
    expect(asMove(start, "rnbqkbnr/pppppppp/8/4P3/8/8/PPPP1PPP/RNBQKBNR")).toBeNull();
    expect(asMove(start, "rnbqkbnr/pppp1ppp/8/4p3/8/8/PPPPPPPP/RNBQKBNR")).toBeNull();
  });

  test("a move chosen in the explorer is played", () => {
    expect(playMove(start, "e2e4")).toEqual({ board: afterE4, turn: "black" });
    expect(playMove(start, "e2e5")).toBeNull();
  });
});
