import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";
import { formatGameDate } from "../games";
import type { Puzzle } from "./training";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

function aPuzzle(fields: Partial<Puzzle> = {}): Puzzle {
  return {
    id: 5,
    card_id: 9,
    game: {
      id: 7,
      white: "alice64",
      black: "bob_b",
      date_pgn: "2026.10.01",
      eco: "C50",
      opening: "Italian Game",
      user_color: "white",
    },
    ply: 6,
    kind: "found",
    // Scholar's Mate, before 4. Qxf7#.
    fen: "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
    last_move_uci: "g8f6",
    solution: ["h5f7"],
    themes: ["mate", "mateIn1"],
    win_swing: 45,
    due_at: "2026-10-23T08:00:00Z",
    ...fields,
  };
}

/**
 * A simulated training API: the next puzzles one after another (then nothing is due), reviews
 * rated Easy when right and Again when wrong. Returns what it received.
 */
function simulateTraining(...puzzles: Puzzle[]) {
  const received: { queries: string[]; reviews: unknown[]; ratings: unknown[] } = {
    queries: [],
    reviews: [],
    ratings: [],
  };
  let index = 0;
  server.use(
    http.get("*/api/v1/training/next", ({ request }) => {
      received.queries.push(new URL(request.url).search);
      const puzzle = puzzles[index] ?? null;
      return HttpResponse.json({ puzzle, due: puzzles.length - index });
    }),
    http.get("*/api/v1/training/stats", () =>
      HttpResponse.json({
        puzzles: 12,
        due_now: puzzles.length,
        due_today: puzzles.length,
        reviewed_today: index,
        weeks: [{ week: "2026-10-19", reviews: 4, solved: 3 }],
      }),
    ),
    http.post("*/api/v1/training/reviews", async ({ request }) => {
      const body = (await request.json()) as { correct: boolean };
      received.reviews.push(body);
      index += 1;
      const rating = body.correct ? 4 : 1;
      return HttpResponse.json(
        { id: 3, rating, correct: body.correct, next_due_at: "2026-10-30T08:00:00Z" },
        { status: 201 },
      );
    }),
    http.patch("*/api/v1/training/reviews/:id", async ({ request }) => {
      const body = (await request.json()) as { rating: number };
      received.ratings.push(body);
      return HttpResponse.json({
        id: 3,
        rating: body.rating,
        correct: true,
        next_due_at: "2026-10-24T08:00:00Z",
      });
    }),
  );
  return received;
}

function openTraining(path = "/train") {
  simulateAuth(alice, { loggedIn: true });
  renderApp(path);
}

async function play(move: string) {
  const user = userEvent.setup();
  await user.type(await screen.findByRole("textbox", { name: "Your move" }), move);
  await user.click(screen.getByRole("button", { name: "Play" }));
}

test("the link to the puzzle's game shows what is known of its date", async () => {
  const puzzle = aPuzzle();
  simulateTraining(aPuzzle({ game: { ...puzzle.game, date_pgn: "1960.??.??" } }));
  openTraining();

  expect(
    await screen.findByRole("link", { name: "From your game alice64 – bob_b, 1960" }),
  ).toBeInTheDocument();
});

test("without a date the link leaves it out", async () => {
  const puzzle = aPuzzle();
  simulateTraining(aPuzzle({ game: { ...puzzle.game, date_pgn: "????.??.??" } }));
  openTraining();

  expect(
    await screen.findByRole("link", { name: "From your game alice64 – bob_b" }),
  ).toBeInTheDocument();
});

test("solving a puzzle records it and offers the rating to change", async () => {
  const received = simulateTraining(aPuzzle());
  openTraining();

  expect(
    await screen.findByRole("heading", { name: "Find the best move for White" }),
  ).toBeVisible();
  expect(screen.getByText("Your opponent blundered, and you punished it.")).toBeVisible();
  expect(
    screen.getByRole("link", {
      name: `From your game alice64 – bob_b, ${formatGameDate("2026.10.01")}`,
    }),
  ).toHaveAttribute("href", "/games/7");
  await play("Qxf7#");

  expect(await screen.findByText("Solved!")).toBeVisible();
  await waitFor(() => {
    expect(received.reviews).toMatchObject([{ card_id: 9, correct: true }]);
  });
  const ratings = await screen.findByRole("group", { name: /How was it/ });
  expect(within(ratings).getByRole("button", { name: "Easy" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await userEvent.setup().click(within(ratings).getByRole("button", { name: "Hard" }));

  await waitFor(() => {
    expect(within(ratings).getByRole("button", { name: "Hard" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
  expect(received.ratings).toEqual([{ rating: 2 }]);
});

test("a wrong move fails the puzzle; the solution can be shown", async () => {
  const received = simulateTraining(aPuzzle());
  openTraining();

  await play("Qxe5+");
  expect(await screen.findByText("That's not it. Try again, or show the solution.")).toBeVisible();
  await userEvent.setup().click(screen.getByRole("button", { name: "Show the solution" }));

  expect(await screen.findByText("The solution: 4. Qxf7#")).toBeVisible();
  await waitFor(() => {
    expect(received.reviews).toEqual([expect.objectContaining({ correct: false })]);
  });
});

test("impossible moves are explained, not played", async () => {
  const received = simulateTraining(aPuzzle());
  openTraining();

  await play("Qh8");

  expect(await screen.findByText(/That move isn't possible here/)).toBeVisible();
  expect(received.reviews).toEqual([]);
});

test("the opponent replies, and the user goes on", async () => {
  simulateTraining(
    aPuzzle({
      fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      last_move_uci: "",
      solution: ["e2e4", "e7e5", "g1f3"],
    }),
  );
  openTraining();

  await play("e4");
  // The reply comes after a moment; then it's the user's turn again.
  expect(
    await screen.findByRole("textbox", { name: "Your move" }, { timeout: 2000 }),
  ).toBeVisible();
  await play("Nf3");

  expect(await screen.findByText("Solved!")).toBeVisible();
});

test("the next puzzle, then nothing due", async () => {
  simulateTraining(aPuzzle());
  openTraining();

  await play("Qxf7#");
  await userEvent.setup().click(await screen.findByRole("button", { name: "Next puzzle" }));

  expect(await screen.findByText(/Nothing to train right now/)).toBeVisible();
});

test("filters choose the puzzles", async () => {
  const received = simulateTraining(aPuzzle());
  openTraining("/train?kind=missed&theme=mate");

  await screen.findByRole("heading", { name: "Find the best move for White" });

  expect(received.queries[0]).toContain("kind=missed");
  expect(received.queries[0]).toContain("theme=mate");
});

test("shows what is due and how training went this week", async () => {
  simulateTraining(aPuzzle());
  openTraining();

  expect(
    await screen.findByText("1 due · 0 done today · 12 puzzles in all · 75 % solved this week"),
  ).toBeVisible();
});

test("the header leads to training", async () => {
  simulateTraining();
  simulateAuth(alice, { loggedIn: true });
  renderApp("/games-that-dont-exist");

  await userEvent.setup().click(await screen.findByRole("link", { name: "Train" }));

  expect(await screen.findByRole("heading", { name: "Train with your own puzzles" })).toBeVisible();
});
