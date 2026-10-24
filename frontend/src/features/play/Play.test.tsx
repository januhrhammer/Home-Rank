import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";
import type { BotGame, NewGame } from "./play";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };
const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const AFTER_E4_C5 = "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2";

function aGame(fields: Partial<BotGame> = {}): BotGame {
  return {
    id: 3,
    start_fen: START,
    start_label: "",
    user_color: "white",
    opponent: "maia",
    opponent_elo: 1500,
    opponent_name: "Maia 1500",
    moves: [],
    fen: START,
    status: "playing",
    result: "",
    termination: null,
    clock: null,
    created_at: "2026-10-24T10:00:00Z",
    finished_at: null,
    saved_game_id: null,
    ...fields,
  };
}

/** The play API with one game; moves are answered with `reply`, the bot's next state. */
function simulatePlay(game: BotGame, reply?: BotGame) {
  const received: { started: NewGame[]; moves: string[]; saved: number } = {
    started: [],
    moves: [],
    saved: 0,
  };
  server.use(
    http.get("*/api/v1/repertoires", () => HttpResponse.json([])),
    http.get("*/api/v1/play/opponents", () =>
      HttpResponse.json([
        { opponent: "maia", min_elo: 800, max_elo: 2400 },
        { opponent: "stockfish", min_elo: 1320, max_elo: 3190 },
      ]),
    ),
    http.get("*/api/v1/play/games", () => HttpResponse.json([game])),
    http.post("*/api/v1/play/games", async ({ request }) => {
      received.started.push((await request.json()) as NewGame);
      return HttpResponse.json(game, { status: 201 });
    }),
    http.get("*/api/v1/play/games/3", () => HttpResponse.json(game)),
    http.post("*/api/v1/play/games/3/moves", async ({ request }) => {
      received.moves.push(((await request.json()) as { move_uci: string }).move_uci);
      return HttpResponse.json(reply ?? game);
    }),
    http.post("*/api/v1/play/games/3/save", () => {
      received.saved += 1;
      return HttpResponse.json({ game_id: 42 });
    }),
  );
  return received;
}

test("a new game is started with the side, opponent, rating and clock chosen", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulatePlay(aGame());
  renderApp("/play");
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "New game" }));
  const dialog = await screen.findByRole("dialog");
  await user.click(within(dialog).getByText("Black"));
  await user.click(within(dialog).getByText("Stockfish"));
  await user.click(within(dialog).getByText("10 + 5"));
  await user.click(within(dialog).getByRole("button", { name: "Start" }));

  expect(await screen.findByRole("heading", { name: "You against Maia 1500" })).toBeInTheDocument();
  expect(received.started).toEqual([
    {
      start_fen: START,
      start_label: "",
      user_color: "black",
      opponent: "stockfish",
      opponent_elo: 1500,
      clock: { base_seconds: 600, increment_seconds: 5 },
    },
  ]);
});

test("a typed move is sent, and the bot's answer shown", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulatePlay(aGame(), aGame({ moves: ["e2e4", "c7c5"], fen: AFTER_E4_C5 }));
  renderApp("/play/3");
  const user = userEvent.setup();

  expect(await screen.findByRole("status")).toHaveTextContent("Your move.");
  await user.type(screen.getByRole("textbox", { name: "Type your move" }), "e4{Enter}");

  const moves = await screen.findByRole("list", { name: "Moves" });
  expect(await within(moves).findByText("c5")).toBeInTheDocument();
  expect(moves).toHaveTextContent("1.e4c5");
  expect(received.moves).toEqual(["e2e4"]);
});

test("a finished game says how it ended and can be saved to my games", async () => {
  simulateAuth(alice, { loggedIn: true });
  const finished = aGame({
    moves: ["e2e4", "c7c5"],
    fen: AFTER_E4_C5,
    status: "finished",
    result: "0-1",
    termination: "timeout",
    finished_at: "2026-10-24T10:05:00Z",
  });
  const received = simulatePlay(finished);
  renderApp("/play/3");
  const user = userEvent.setup();

  expect(await screen.findByRole("status")).toHaveTextContent("You lost on time.");
  expect(screen.queryByRole("textbox", { name: "Type your move" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Resign" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Save to my games" }));

  expect(await screen.findByRole("link", { name: "Open it in your games" })).toHaveAttribute(
    "href",
    "/games/42",
  );
  expect(received.saved).toBe(1);
});

test("timed games show both clocks and offer no take-back", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulatePlay(
    aGame({ clock: { base_ms: 300_000, increment_ms: 3_000, white_ms: 245_000, black_ms: 9_300 } }),
  );
  renderApp("/play/3");

  expect(await screen.findByRole("timer", { name: "Maia 1500's clock" })).toHaveTextContent(
    "0:09.3",
  );
  expect(screen.getByRole("timer", { name: "Your clock" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Take back" })).not.toBeInTheDocument();
});

test("someone else's game, or none, isn't found", async () => {
  simulateAuth(alice, { loggedIn: true });
  server.use(
    http.get("*/api/v1/play/games/9", () =>
      HttpResponse.json({ status: 404, detail: "Not Found." }, { status: 404 }),
    ),
  );
  renderApp("/play/9");

  expect(await screen.findByRole("alert")).toHaveTextContent("There is no such game.");
});

test("a note says where the game left the user's repertoire", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulatePlay(
    aGame({
      moves: ["e2e4", "e7e5"],
      fen: "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    }),
  );
  server.use(
    http.get("*/api/v1/repertoires", () =>
      HttpResponse.json([{ id: 4, name: "Open games", color: "white", move_count: 2, due: 0 }]),
    ),
    http.get("*/api/v1/repertoires/4/moves", () =>
      HttpResponse.json([
        {
          id: 1,
          from_position: "1",
          from_fen: START,
          move_uci: "e2e4",
          move_san: "e4",
          to_position: "2",
          comment: "",
          card_id: 9,
        },
        {
          id: 2,
          from_position: "2",
          from_fen: "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
          move_uci: "c7c5",
          move_san: "c5",
          to_position: "3",
          comment: "",
          card_id: null,
        },
      ]),
    ),
  );
  renderApp("/play/3");

  expect(
    await screen.findByText(
      "Maia 1500 left your repertoire “Open games” with 1… e5: you have no reply prepared.",
    ),
  ).toBeInTheDocument();
});
