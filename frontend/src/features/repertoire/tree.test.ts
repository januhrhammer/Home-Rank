import { expect, test } from "vitest";

import { movesOf } from "./testMoves";
import { buildRepertoireTree, lineTo } from "./tree";

function sans(nodes: { san: string }[]): string[] {
  return nodes.map((node) => node.san);
}

test("moves become a tree from the starting position, in the order they were added", () => {
  const tree = buildRepertoireTree(
    movesOf([["d4", "d5", "c4", "e6"], ["d4", "d5", "c4", "c6"], ["e4"]]),
  );

  expect(sans(tree.firstMoves)).toEqual(["d4", "e4"]);
  const c4 = tree.firstMoves[0]?.children[0]?.children[0];
  expect(c4?.san).toBe("c4");
  expect(sans(c4?.children ?? [])).toEqual(["e6", "c6"]);
  expect(c4?.ply).toBe(3);
  expect(c4?.squares).toEqual(["c2", "c4"]);
  expect(c4?.fen).toBe("rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 2");
});

test("a transposed position is shown once, where it is reached first, with a note on the other", () => {
  const tree = buildRepertoireTree(
    movesOf([
      ["c4", "e6", "Nc3", "d5", "d4", "Nf6"], // as long as the other way, and added first
      ["d4", "Nf6", "c4", "e6", "Nc3", "d5"],
    ]),
  );

  const nodes = [...tree.byId.values()];
  const shown = nodes.find((node) => lineTo(node) === "1. c4 e6 2. Nc3 d5 3. d4 Nf6");
  const other = nodes.find((node) => lineTo(node) === "1. d4 Nf6 2. c4 e6 3. Nc3 d5");
  expect(shown).toBeDefined();
  expect(other?.children).toEqual([]);
  expect(other && tree.transposesTo.get(other.id)).toBe(shown);
  expect(other?.commentsAfter).toEqual(["Same position as after 1. c4 e6 2. Nc3 d5 3. d4 Nf6."]);
});

test("a position is shown where the fewest moves reach it", () => {
  // 1. e3 e6 2. e4 e5 reaches the position after 1. e4 e5, in more moves; it is added first.
  const tree = buildRepertoireTree(
    movesOf([
      ["e3", "e6", "e4", "e5", "Nf3"],
      ["e4", "e5"],
    ]),
  );

  const nf3 = [...tree.byId.values()].find((node) => node.san === "Nf3");
  expect(nf3 && lineTo(nf3)).toBe("1. e4 e5 2. Nf3");
  const longWay = tree.firstMoves[0]?.children[0]?.children[0]?.children[0];
  expect(longWay?.commentsAfter).toEqual(["Same position as after 1. e4 e5."]);
});

test("transposition notes are written in the notation asked for", () => {
  const tree = buildRepertoireTree(
    movesOf([
      ["Nf3", "d5", "d4"],
      ["d4", "d5", "Nf3"],
    ]),
    (san) => san.replace("N", "♘"),
  );

  const notes = [...tree.byId.values()].flatMap((node) => node.commentsAfter);
  expect(notes).toEqual(["Same position as after 1. ♘f3 d5 2. d4."]);
});

test("comments come with their moves", () => {
  const tree = buildRepertoireTree(movesOf([["d4", "d5"]], { comments: { d5: "Solid." } }));

  expect(tree.firstMoves[0]?.children[0]?.commentsAfter).toEqual(["Solid."]);
});

test("a line back to the starting position ends there without a note", () => {
  const tree = buildRepertoireTree(movesOf([["Nf3", "Nf6", "Ng1", "Ng8"]]));

  const ng8 = tree.firstMoves[0]?.children[0]?.children[0]?.children[0];
  expect(ng8?.san).toBe("Ng8");
  expect(ng8?.children).toEqual([]);
  expect(ng8?.commentsAfter).toEqual([]);
});

test("an empty repertoire has no moves", () => {
  expect(buildRepertoireTree([]).firstMoves).toEqual([]);
});

test("a line is written with move numbers, figurines if asked for", () => {
  const tree = buildRepertoireTree(movesOf([["e4", "e5", "Nf3"]]));
  const nf3 = tree.firstMoves[0]?.children[0]?.children[0];

  expect(nf3 && lineTo(nf3)).toBe("1. e4 e5 2. Nf3");
  const e5 = tree.firstMoves[0]?.children[0];
  expect(e5 && lineTo(e5, (san) => san.toLowerCase())).toBe("1. e4 e5");
});
