import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";
import type { Game } from "./games";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

const PGN = `[White "Anna"]
[Black "Ben"]
[Result "*"]

1. e4 e5 (1... c5 2. Nf3) 2. Nf3 *
`;

function aGame(pgn: string): Game {
  return {
    id: 7,
    white: "Anna",
    black: "Ben",
    white_elo: null,
    black_elo: null,
    result: "*",
    date: null,
    date_pgn: "????.??.??",
    event: "",
    site: "",
    eco: "",
    opening: "",
    time_control: "",
    time_class: "unknown",
    user_color: "white",
    ply_count: 3,
    source: "pgn",
    imported_at: "2026-10-22T12:00:00Z",
    tags: [],
    pgn,
    import_run_id: null,
    collections: [],
  };
}

/** The viewer of one game; saved annotations come back as the stored game, like the server. */
function openGame() {
  let stored = PGN;
  const saved: string[] = [];
  server.use(
    http.get("*/api/v1/games/7", () => HttpResponse.json(aGame(stored))),
    http.put("*/api/v1/games/7/annotations", async ({ request }) => {
      stored = ((await request.json()) as { pgn: string }).pgn;
      saved.push(stored);
      return HttpResponse.json(aGame(stored));
    }),
    http.get("*/api/v1/tags", () => HttpResponse.json({ items: [], total: 0 })),
    http.get("*/api/v1/collections", () => HttpResponse.json({ items: [], total: 0 })),
    http.get("*/api/v1/analysis/games/7", () =>
      HttpResponse.json({
        run: null,
        summary: null,
        positions: [],
        white: { inaccuracies: 0, mistakes: 0, blunders: 0 },
        black: { inaccuracies: 0, mistakes: 0, blunders: 0 },
      }),
    ),
  );
  simulateAuth(alice, { loggedIn: true });
  renderApp("/games/7");
  return saved;
}

const flat = (pgn: string | undefined) => (pgn ?? "").split("\n\n")[1]?.replace(/\s+/g, " ").trim();

test("a comment and a mark on a move are saved", async () => {
  const saved = openGame();
  const user = userEvent.setup();

  await user.click(await screen.findByText("Annotate"));
  const moves = screen.getByRole("group", { name: "Moves" });
  await user.click(within(moves).getByRole("button", { name: "e5" }));
  await user.type(screen.getByRole("textbox", { name: "Comment on 1… e5" }), "Symmetrical.");
  await user.click(screen.getByRole("button", { name: "Save comment" }));
  expect(await within(moves).findByText("Symmetrical.")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Interesting move" }));

  expect(
    await screen.findByRole("button", { name: "Interesting move", pressed: true }),
  ).toBeInTheDocument();
  expect(flat(saved.at(-1))).toBe("1. e4 e5 $5 { Symmetrical. } ( 1... c5 2. Nf3 ) 2. Nf3 *");
});

test("a variation is deleted as a whole; the game's own moves have no delete", async () => {
  const saved = openGame();
  const user = userEvent.setup();

  await user.click(await screen.findByText("Annotate"));
  const moves = screen.getByRole("group", { name: "Moves" });
  await user.click(within(moves).getByRole("button", { name: "e4" }));
  expect(screen.queryByRole("button", { name: "Delete this variation" })).not.toBeInTheDocument();

  // The variation's 2. Nf3 is written before the game's own (1. e4 e5 (1… c5 2. Nf3) 2. Nf3).
  const [inVariation] = within(moves).getAllByRole("button", { name: "Nf3" });
  if (inVariation === undefined) {
    throw new Error("no variation");
  }
  await user.click(inVariation);
  await user.click(screen.getByRole("button", { name: "Delete this variation" }));

  expect(await within(moves).findByRole("button", { name: "Nf3" })).toBeInTheDocument();
  expect(within(moves).queryByRole("button", { name: "c5" })).not.toBeInTheDocument();
  expect(flat(saved.at(-1))).toBe("1. e4 e5 2. Nf3 *");
});

test("without annotation mode nothing can be changed", async () => {
  openGame();

  expect(await screen.findByText("Annotate")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save comment" })).not.toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "Mark the move" })).not.toBeInTheDocument();
});
