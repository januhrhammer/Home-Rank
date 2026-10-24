import { expect, test } from "vitest";

import { type BookMove, departure } from "./departure";
import { playedMoves } from "./moves";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";
const AFTER_E4_C5 = "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2";

// A repertoire for White: 1. e4, and against 1… c5 2. Nf3.
const BOOK: BookMove[] = [
  { repertoire: "Open games", fromFen: START, moveUci: "e2e4", moveSan: "e4" },
  { repertoire: "Open games", fromFen: AFTER_E4_C5, moveUci: "g1f3", moveSan: "Nf3" },
  { repertoire: "Open games", fromFen: AFTER_E4, moveUci: "c7c5", moveSan: "c5" },
];

const game = (...moves: string[]) => playedMoves(START, moves);

test("a game that keeps to the repertoire hasn't left it", () => {
  expect(departure(START, game("e2e4", "c7c5", "g1f3"), BOOK, "white")).toBeNull();
});

test("the user's own move out of the repertoire, with what it has instead", () => {
  const left = departure(START, game("e2e4", "c7c5", "b1c3"), BOOK, "white");

  expect(left).toMatchObject({ byUser: true, repertoire: "Open games", expected: ["Nf3"] });
  expect(left?.move.san).toBe("Nc3");
});

test("the bot's reply the repertoire doesn't cover", () => {
  const left = departure(START, game("e2e4", "e7e5"), BOOK, "white");

  expect(left).toMatchObject({ byUser: false, expected: ["c5"] });
  expect(left?.move.san).toBe("e5");
});

test("a game from a position the repertoire doesn't have says nothing", () => {
  expect(departure(AFTER_E4_C5, playedMoves(AFTER_E4_C5, ["d2d4"]), [], "white")).toBeNull();
  expect(departure(START, game("d2d4"), [], "white")).toBeNull();
});

test("positions match whatever their move counters say", () => {
  // The same position after 1. e4 c5, reached with other counters.
  const book: BookMove[] = [
    {
      repertoire: "Sicilian",
      fromFen: AFTER_E4_C5.replace(" 0 2", " 4 7"),
      moveUci: "g1f3",
      moveSan: "Nf3",
    },
  ];

  expect(departure(AFTER_E4_C5, playedMoves(AFTER_E4_C5, ["b1c3"]), book, "white")).toMatchObject({
    byUser: true,
    expected: ["Nf3"],
  });
});
