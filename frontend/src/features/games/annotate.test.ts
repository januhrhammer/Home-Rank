import { expect, test } from "vitest";

import {
  addMoves,
  deleteVariation,
  isMainLine,
  setComment,
  toggleMark,
  variationStart,
} from "./annotate";
import { buildMoveTree, nodeAtPath } from "./moveTree";

const PGN = `[White "Anna"]
[Black "Ben"]
[Result "1-0"]

1. e4 { [%clk 0:03:00] } e5 2. Nf3 Nc6 3. Bb5 1-0`;

/** The moves as text, without line breaks. */
const flat = (pgn: string) => pgn.split("\n\n")[1]?.replace(/\s+/g, " ").trim();

test("a comment is set, keeping the clock; an empty one removes the text", () => {
  const commented = setComment(PGN, [0], "Best by test.");
  expect(flat(commented)).toBe("1. e4 { Best by test. [%clk 0:03:00] } e5 2. Nf3 Nc6 3. Bb5 1-0");

  const plain = setComment(setComment(PGN, [0, 0], "Solid."), [0, 0], "");
  expect(flat(plain)).toBe("1. e4 { [%clk 0:03:00] } e5 2. Nf3 Nc6 3. Bb5 1-0");
});

test("a mark replaces another of its kind, and goes again when chosen again", () => {
  const good = toggleMark(PGN, [0, 0, 0], 1); // 2. Nf3!
  const better = toggleMark(toggleMark(good, [0, 0, 0], 3), [0, 0, 0], 16); // !! and ±
  const none = toggleMark(toggleMark(better, [0, 0, 0], 3), [0, 0, 0], 16);

  expect(flat(good)).toContain("2. Nf3 $1 2... Nc6");
  expect(flat(better)).toContain("2. Nf3 $3 $16 2... Nc6");
  expect(flat(none)).toContain("2. Nf3 Nc6");
});

test("moves the line has are followed; new ones become a variation", () => {
  const followed = addMoves(PGN, [0], ["e7e5", "g1f3"]);
  expect(followed.path).toEqual([0, 0, 0]);
  expect(flat(followed.pgn)).toBe(flat(PGN)); // nothing new

  const added = addMoves(PGN, [0, 0], ["f2f4", "e5f4"]); // 2. f4 exf4 instead of 2. Nf3
  expect(added.path).toEqual([0, 0, 1, 0]);
  expect(flat(added.pgn)).toBe(
    "1. e4 { [%clk 0:03:00] } e5 2. Nf3 ( 2. f4 exf4 ) 2... Nc6 3. Bb5 1-0",
  );
  const tree = buildMoveTree(added.pgn);
  expect(tree && nodeAtPath(tree, added.path)?.san).toBe("exf4");
});

test("a first move of its own is a variation from the start", () => {
  const added = addMoves(PGN, [], ["d2d4"]);

  expect(added.path).toEqual([1]);
  expect(flat(added.pgn)).toMatch(/^1\. e4 .*\( 1\. d4 \)/);
});

test("illegal moves are refused", () => {
  expect(() => addMoves(PGN, [0], ["e2e4"])).toThrow("illegal move e2e4");
});

test("a variation is deleted as a whole, from any of its moves; the game's own moves stay", () => {
  const added = addMoves(PGN, [0, 0], ["f2f4", "e5f4", "g1f3"]); // 2. f4 exf4 3. Nf3

  expect(added.path).toEqual([0, 0, 1, 0, 0]);
  expect(variationStart(added.path)).toEqual([0, 0, 1]);
  expect(flat(deleteVariation(added.pgn, added.path))).toBe(
    "1. e4 { [%clk 0:03:00] } e5 2. Nf3 Nc6 3. Bb5 1-0",
  );
  expect(isMainLine([0, 0, 0])).toBe(true);
  expect(isMainLine(added.path)).toBe(false);
  expect(() => deleteVariation(PGN, [0, 0])).toThrow();
});
