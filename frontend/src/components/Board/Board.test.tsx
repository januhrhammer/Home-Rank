import { render, screen, waitFor } from "@testing-library/react";
import { expect, test } from "vitest";

import { Board } from "./Board";

const KINGS_ONLY = "8/8/8/8/8/8/8/K6k w - - 0 1";
const KINGS_AND_QUEEN = "8/8/8/8/3Q4/8/8/K6k w - - 0 1";

// chessground draws its own <piece> elements, which have no accessible role, so these tests
// look at them directly: "white king" is a <piece class="white king">. The hidden "ghost"
// piece, shown where a dragged piece came from, isn't on the board.
function pieces(): string[] {
  const board = screen.getByRole("img", { name: "Chess board" });
  return [...board.querySelectorAll("piece:not(.ghost)")].map((piece) => piece.className);
}

test("shows the given position right away, without animating from the starting position", () => {
  render(<Board fen={KINGS_ONLY} />);

  expect(pieces().sort()).toEqual(["black king", "white king"]);
});

test("follows a change of position", async () => {
  const { rerender } = render(<Board fen={KINGS_ONLY} />);

  rerender(<Board fen={KINGS_AND_QUEEN} />);

  // chessground redraws on the next animation frame, not immediately.
  await waitFor(() => {
    expect(pieces()).toContainEqual(expect.stringContaining("white queen"));
  });
});

test("can be shown from black's side", () => {
  render(<Board fen={KINGS_ONLY} orientation="black" />);

  expect(screen.getByRole("img", { name: "Chess board" })).toHaveClass("orientation-black");
});

test("highlights the last move's squares", () => {
  render(<Board fen={KINGS_AND_QUEEN} lastMove={["d1", "d4"]} />);

  const board = screen.getByRole("img", { name: "Chess board" });
  expect(board.querySelectorAll("square.last-move")).toHaveLength(2);
});

test("describes the position for screen readers", () => {
  render(<Board fen={KINGS_ONLY} label="Position after 40. Kb1" />);

  expect(screen.getByRole("img", { name: "Position after 40. Kb1" })).toBeInTheDocument();
});
