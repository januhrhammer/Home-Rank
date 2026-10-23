import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";
import type { DrillStep, Gap } from "./drill";
import type { Repertoire } from "./repertoire";
import { movesOf } from "./testMoves";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };
const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const AFTER_D4_D5 = "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2";
const AFTER_D4 = "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1";
const AFTER_C4 = "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 2";

const QUEENS_GAMBIT: Repertoire = {
  id: 4,
  name: "Queen's Gambit",
  color: "white",
  move_count: 3,
  due: 2,
};

function aStep(fields: Partial<DrillStep>): DrillStep {
  return {
    move_id: 1,
    fen: START,
    move_uci: "d2d4",
    move_san: "d4",
    comment: "",
    card_id: 101,
    due: true,
    other_moves: [],
    ...fields,
  };
}

const LINE: DrillStep[] = [
  aStep({ move_id: 1, comment: "The queen's pawn." }),
  aStep({ move_id: 2, fen: AFTER_D4, move_uci: "d7d5", move_san: "d5", card_id: null }),
  aStep({ move_id: 3, fen: AFTER_D4_D5, move_uci: "c2c4", move_san: "c4", card_id: 103 }),
];

/**
 * A simulated drill API: the due cards one after another (one per GET after a review), the
 * line, and reviews rated Good when right and Again when wrong. Returns what it received.
 */
function simulateDrill({
  due = [] as { step: DrillStep; last_move_uci: string }[],
  line = LINE,
  gaps = [] as Gap[],
}) {
  const received: {
    reviews: unknown[];
    ratings: unknown[];
    lineQueries: string[];
    added: unknown[];
  } = { reviews: [], ratings: [], lineQueries: [], added: [] };
  let index = 0;
  server.use(
    http.get("*/api/v1/repertoires/:id", () => HttpResponse.json(QUEENS_GAMBIT)),
    http.get("*/api/v1/repertoires/:id/drill/next", () => {
      const card = due[index];
      return HttpResponse.json(
        card ? { ...card, due: due.length - index } : { step: null, last_move_uci: "", due: 0 },
      );
    }),
    http.get("*/api/v1/repertoires/:id/drill/line", ({ request }) => {
      received.lineQueries.push(new URL(request.url).search);
      return HttpResponse.json(line);
    }),
    http.post("*/api/v1/training/reviews", async ({ request }) => {
      const body = (await request.json()) as { correct: boolean };
      received.reviews.push(body);
      index += 1;
      return HttpResponse.json(
        {
          id: 50 + index,
          rating: body.correct ? 3 : 1,
          correct: body.correct,
          next_due_at: "2026-10-30T08:00:00Z",
        },
        { status: 201 },
      );
    }),
    http.patch("*/api/v1/training/reviews/:id", async ({ request }) => {
      const body = (await request.json()) as { rating: number };
      received.ratings.push(body);
      return HttpResponse.json({
        id: 51,
        rating: body.rating,
        correct: true,
        next_due_at: "2026-11-02T08:00:00Z",
      });
    }),
    http.get("*/api/v1/repertoires/:id/gaps", () => HttpResponse.json(gaps)),
    http.get("*/api/v1/repertoires/:id/moves", () =>
      HttpResponse.json(movesOf([["d4", "d5", "c4", "e6"]])),
    ),
    http.post("*/api/v1/repertoires/:id/moves", async ({ request }) => {
      received.added.push(await request.json());
      return HttpResponse.json(movesOf([["d4"]])[0], { status: 201 });
    }),
  );
  return received;
}

async function typeMove(text: string) {
  const user = userEvent.setup();
  const field = await screen.findByLabelText("Your move");
  await user.clear(field);
  await user.type(field, text);
  await user.click(screen.getByRole("button", { name: "Play" }));
}

test("a due card is answered, rated Good, and the rating can be changed", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateDrill({
    due: [
      { step: aStep({}), last_move_uci: "" },
      {
        step: aStep({
          move_id: 3,
          fen: AFTER_D4_D5,
          move_uci: "c2c4",
          move_san: "c4",
          card_id: 103,
        }),
        last_move_uci: "d7d5",
      },
    ],
  });
  renderApp("/repertoires/4/drill");
  const user = userEvent.setup();

  expect(
    await screen.findByText("Your move with White: what does your repertoire play?"),
  ).toBeInTheDocument();
  expect(screen.getByText("2 due")).toBeInTheDocument();
  await typeMove("d4");

  expect(screen.getByRole("status")).toHaveTextContent("Right: d4");
  const ratings = await screen.findByRole("group", { name: /How was it/ });
  expect(within(ratings).getByRole("button", { name: "Good" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await user.click(within(ratings).getByRole("button", { name: "Hard" }));
  expect(received.ratings).toEqual([{ rating: 2 }]);

  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(await screen.findByText("1 due")).toBeInTheDocument();
  expect(received.reviews).toEqual([
    { card_id: 101, correct: true, elapsed_ms: expect.any(Number) as number },
  ]);
});

test("a wrong move shows the repertoire's move and counts as Again", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateDrill({ due: [{ step: aStep({}), last_move_uci: "" }] });
  renderApp("/repertoires/4/drill");

  await typeMove("e4");

  expect(screen.getByRole("status")).toHaveTextContent("Not that. Your repertoire plays d4");
  expect(screen.getByRole("img", { name: "Drill position" })).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Again" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(received.reviews).toEqual([
    { card_id: 101, correct: false, elapsed_ms: expect.any(Number) as number },
  ]);
  expect(screen.queryByLabelText("Your move")).not.toBeInTheDocument();
});

test("another move of the repertoire's isn't wrong: the other one is asked for", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateDrill({
    due: [{ step: aStep({ other_moves: ["g1f3"] }), last_move_uci: "" }],
  });
  renderApp("/repertoires/4/drill");

  await typeMove("Nf3");
  expect(screen.getByRole("status")).toHaveTextContent("That's in your repertoire too");
  expect(received.reviews).toEqual([]);

  await typeMove("d4");
  expect(screen.getByRole("status")).toHaveTextContent("Right: d4");
  expect(received.reviews).toEqual([
    { card_id: 101, correct: true, elapsed_ms: expect.any(Number) as number },
  ]);
});

test("with nothing due, whole lines are offered", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateDrill({});
  renderApp("/repertoires/4/drill");

  expect(await screen.findByText(/Nothing is due/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Play whole lines instead." })).toHaveAttribute(
    "href",
    "/repertoires/4/drill?mode=line",
  );
});

test("a whole line: my moves are asked for, the opponent's played for me", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateDrill({});
  renderApp("/repertoires/4/drill?mode=line&through=3");
  const user = userEvent.setup();

  expect(await screen.findByRole("link", { name: "Whole lines" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await typeMove("d4");
  expect(screen.getByText("The queen's pawn.")).toBeInTheDocument();

  // The answer stays a moment, then the opponent replies 1… d5 by itself.
  expect(await screen.findByText(/Your opponent moves/, {}, { timeout: 3000 })).toBeInTheDocument();
  await typeMove("Bf4");
  expect(screen.getByRole("status")).toHaveTextContent("Not that. Your repertoire plays c4");

  expect(
    await screen.findByText("Line done: 1 of 2 moves right.", {}, { timeout: 3000 }),
  ).toBeInTheDocument();
  expect(received.reviews).toEqual([
    { card_id: 101, correct: true, elapsed_ms: expect.any(Number) as number },
    { card_id: 103, correct: false, elapsed_ms: expect.any(Number) as number },
  ]);
  expect(received.lineQueries).toEqual(["?through=3"]);

  await user.click(screen.getByRole("button", { name: "Next line" }));
  expect(await screen.findByText(/what does your repertoire play/)).toBeInTheDocument();
  expect(received.lineQueries).toEqual(["?through=3", ""]);
});

test("the gap report says where my games left the repertoire, and adds a reply", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateDrill({
    gaps: [
      {
        fen: AFTER_C4,
        move_uci: "c7c6",
        move_san: "c6",
        by_user: false,
        games: 3,
        game_ids: [70, 61],
        last_played: "2026-09-14",
      },
      {
        fen: START,
        move_uci: "e2e4",
        move_san: "e4",
        by_user: true,
        games: 1,
        game_ids: [55],
        last_played: null,
      },
    ],
  });
  renderApp("/repertoires/4/gaps");
  const user = userEvent.setup();

  const items = await screen.findAllByRole("listitem");
  expect(items[0]).toHaveTextContent("After 1. d4 d5 2. c4: c6");
  expect(items[0]).toHaveTextContent("Not covered · 3 games · last 2026-09-14");
  expect(items[1]).toHaveTextContent("First move: e4");
  expect(items[1]).toHaveTextContent("You left your repertoire · 1 games");
  expect(
    within(items[0] as HTMLElement).getByRole("link", { name: "Latest game" }),
  ).toHaveAttribute("href", "/games/70");
  expect(screen.getByRole("img", { name: "Position after the gap move c6" })).toBeInTheDocument();

  await user.click(within(items[1] as HTMLElement).getByRole("button", { name: /e4/ }));
  expect(screen.getByRole("img", { name: "Position after the gap move e4" })).toBeInTheDocument();

  await user.click(within(items[0] as HTMLElement).getByRole("button", { name: "Add this reply" }));
  expect(received.added).toEqual([{ fen: AFTER_C4, move_uci: "c7c6" }]);
});

test("no gaps", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateDrill({});
  renderApp("/repertoires/4/gaps");

  expect(await screen.findByText(/No gaps/)).toBeInTheDocument();
});
