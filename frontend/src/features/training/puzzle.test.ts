import { describe, expect, test } from "vitest";

import { begin, boardMove, reply, replyDue, showSolution, tryMove, typedMove } from "./puzzle";

// Scholar's Mate, before 4. Qxf7#.
const MATE_IN_ONE = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4";
// A back rank: Rxd8 mates at once.
const BACK_RANK = "3r2k1/5ppp/8/8/8/8/5PPP/3RR1K1 w - - 0 1";
const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
// The mechanics of a longer solution, with any legal moves.
const LINE = ["e2e4", "e7e5", "g1f3"];

describe("solving", () => {
  test("the solution's move is right and ends a one-move puzzle", () => {
    const solved = tryMove(begin(MATE_IN_ONE, "g8f6"), ["h5f7"], "h5f7");

    expect(solved.status).toBe("solved");
    expect(solved.wrong).toBe(false);
    expect(solved.lastMove).toEqual(["h5", "f7"]);
  });

  test("a wrong move isn't played but fails the puzzle; the right one still solves it", () => {
    const start = begin(MATE_IN_ONE, "g8f6");

    const wrong = tryMove(start, ["h5f7"], "h5e5");
    expect(wrong.fen).toBe(MATE_IN_ONE);
    expect(wrong.wrong).toBe(true);

    const solved = tryMove(wrong, ["h5f7"], "h5f7");
    expect(solved.status).toBe("solved");
    expect(solved.wrong).toBe(true);
  });

  test("another mating move is as good as the solution's", () => {
    // The solution starts with a quieter move; Rxd8 mates at once.
    const solution = ["e1e8", "d8e8", "g2g3"];

    const solved = tryMove(begin(BACK_RANK, ""), solution, "d1d8");

    expect(solved.status).toBe("solved");
    expect(solved.wrong).toBe(false);
  });

  test("the opponent's reply follows a right move, then the user goes on", () => {
    let progress = tryMove(begin(START, ""), LINE, "e2e4");
    expect(progress.status).toBe("playing");
    expect(replyDue(progress, LINE)).toBe(true);

    progress = reply(progress, LINE);
    expect(progress.lastMove).toEqual(["e7", "e5"]);
    expect(replyDue(progress, LINE)).toBe(false);

    progress = tryMove(progress, LINE, "g1f3");
    expect(progress.status).toBe("solved");
  });

  test("giving up shows the whole solution and fails the puzzle", () => {
    const shown = showSolution(begin(START, ""), LINE);

    expect(shown.status).toBe("shown");
    expect(shown.wrong).toBe(true);
    expect(shown.lastMove).toEqual(["g1", "f3"]);
  });
});

describe("moves", () => {
  test("typed moves may be SAN or UCI, and must be legal", () => {
    expect(typedMove(MATE_IN_ONE, "Qxf7#")).toBe("h5f7");
    expect(typedMove(MATE_IN_ONE, " qxf7 ")).toBe(null); // SAN pieces are capitals
    expect(typedMove(MATE_IN_ONE, "h5f7")).toBe("h5f7");
    expect(typedMove(MATE_IN_ONE, "Qh8")).toBe(null);
  });

  test("a pawn reaching the last rank becomes what the solution asks for, else a queen", () => {
    const promotion = "8/4P1k1/8/8/8/8/6K1/8 w - - 0 1";

    expect(boardMove(promotion, "e7", "e8", "e7e8n")).toBe("e7e8n");
    expect(boardMove(promotion, "e7", "e8", "g2g3")).toBe("e7e8q");
    expect(boardMove(promotion, "g2", "g3", "e7e8q")).toBe("g2g3");
  });
});
