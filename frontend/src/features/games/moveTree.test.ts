import { expect, test } from "vitest";

import { buildMoveTree, endOfLine, type MoveNode, moveNumber, type MoveTree } from "./moveTree";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

function tree(pgn: string): MoveTree {
  const result = buildMoveTree(pgn);
  if (result === null) {
    throw new Error("PGN not readable");
  }
  return result;
}

/** The moves of the line starting with `first`, following each first continuation. */
function line(first: MoveNode | undefined): string[] {
  const sans: string[] = [];
  for (let node = first; node !== undefined; node = node.children[0]) {
    sans.push(node.san);
  }
  return sans;
}

test("the main line, with the position after each move", () => {
  const { startFen, firstMoves } = tree("1. e4 e5 2. Nf3 *");

  expect(startFen).toBe(START);
  expect(line(firstMoves[0])).toEqual(["e4", "e5", "Nf3"]);
  const e4 = firstMoves[0];
  expect(e4?.fen).toBe("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1");
  expect(e4?.squares).toEqual(["e2", "e4"]);
  expect(e4?.ply).toBe(1);
});

test("variations branch off where they are played", () => {
  const { firstMoves } = tree("1. e4 e5 (1... c5 2. Nf3 (2. c3)) 2. Nf3 *");

  const e5 = firstMoves[0]?.children[0];
  const c5 = firstMoves[0]?.children[1];
  expect(e5?.san).toBe("e5");
  expect(line(c5)).toEqual(["c5", "Nf3"]);
  expect(c5?.children.map((move) => move.san)).toEqual(["Nf3", "c3"]);
  // A variation's position follows its own moves, not the main line's.
  expect(c5?.fen).toContain("pp1ppppp/8/2p5/4P3");
});

test("comments, without commands such as clock times", () => {
  const { firstMoves, gameComments } = tree(
    "{ A quiet game } 1. e4 { [%clk 0:03:00] Best by test } { [%eval 0.3] } e5 *",
  );

  expect(gameComments).toEqual(["A quiet game"]);
  expect(firstMoves[0]?.commentsAfter).toEqual(["Best by test"]);
});

test("annotations become the usual symbols", () => {
  const { firstMoves } = tree("1. e4! e5?! 2. Qh5 $4 $16 *");

  const symbols = [];
  for (let node = firstMoves[0]; node !== undefined; node = node.children[0]) {
    symbols.push(node.symbols.join(""));
  }
  expect(symbols).toEqual(["!", "?!", "??±"]);
});

test("a game from a set-up position, with Black to move", () => {
  const { firstMoves } = tree(
    '[SetUp "1"]\n[FEN "4k3/8/8/8/8/8/4P3/4K3 b - - 0 40"]\n\n40... Kd7 41. e4 *',
  );

  const kd7 = firstMoves[0];
  expect(kd7?.ply).toBe(80); // White's 40th move was the 79th half-move
  expect(kd7 && moveNumber(kd7)).toBe("40…");
  const e4 = kd7?.children[0];
  expect(e4 && moveNumber(e4)).toBe("41.");
});

test("an illegal move in a variation ends that variation", () => {
  const { firstMoves } = tree("1. e4 (1. d4 Qxh7) e5 *");

  expect(line(firstMoves[1])).toEqual(["d4"]);
  expect(line(firstMoves[0])).toEqual(["e4", "e5"]);
});

test("the end of a line", () => {
  const game = tree("1. e4 e5 (1... c5 2. Nf3 d6) 2. Nf3 *");

  expect(endOfLine(game, null)?.san).toBe("Nf3");
  const c5 = game.firstMoves[0]?.children[1] ?? null;
  expect(endOfLine(game, c5)?.san).toBe("d6");
});

test("every move can be found by its id", () => {
  const game = tree("1. e4 e5 (1... c5) *");

  const ids = [...game.byId.values()].map((move) => move.san).sort();
  expect(ids).toEqual(["c5", "e4", "e5"]);
});

test("text that isn't PGN gives no tree", () => {
  expect(buildMoveTree('[FEN "not a position"]\n\n1. e4 *')).toBeNull();
});
