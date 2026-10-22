import { expect, test } from "vitest";

import { withFigurines } from "./notation";

test.each([
  ["Nf3", "♘f3"],
  ["Qxd8+", "♕xd8+"],
  ["Rd8#", "♖d8#"],
  ["Bb5", "♗b5"],
  ["Kxh1", "♔xh1"],
  ["Nbd7", "♘bd7"], // the second letter is a file, not a piece
  ["e4", "e4"],
  ["exd8=Q+", "exd8=♕+"],
  ["b1=N", "b1=♘"],
  ["O-O-O", "O-O-O"],
])("%s is written %s", (san, written) => {
  expect(withFigurines(san)).toBe(written);
});
