import { cleanup, screen } from "@testing-library/react";
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

{ A short game } 1. e4 (1. d4 d5) 1... e5 (1... c5 { The Sicilian } 2. Nf3) 2. Nf3! *
`;

function aGame(fields: Partial<Game> = {}): Game {
  return {
    id: 7,
    white: "Anna",
    black: "Ben",
    white_elo: 1500,
    black_elo: null,
    result: "*",
    date: "2024-03-05",
    date_pgn: "2024.03.05",
    event: "Club night",
    site: "",
    eco: "C40",
    opening: "King's Knight Opening",
    time_control: "",
    time_class: "unknown",
    user_color: "white",
    ply_count: 3,
    source: "pgn",
    imported_at: "2026-10-22T12:00:00Z",
    tags: [{ id: 1, name: "Brilliant" }],
    pgn: PGN,
    import_run_id: null,
    collections: [{ id: 2, name: "Club games" }],
    ...fields,
  };
}

function openGame(game: Game | null) {
  server.use(
    http.get("*/api/v1/games/:gameId", () =>
      game === null ? new HttpResponse(null, { status: 404 }) : HttpResponse.json(game),
    ),
    http.get("*/api/v1/tags", () => HttpResponse.json({ items: [], total: 0 })),
    http.get("*/api/v1/collections", () => HttpResponse.json({ items: [], total: 0 })),
    http.get("*/api/v1/analysis/games/:gameId", () =>
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
}

/** The board, found by what it shows. */
function board(label: string) {
  return screen.getByRole("img", { name: label });
}

test("shows the players, the details and the starting position", async () => {
  openGame(aGame());

  expect(await screen.findByRole("heading", { name: "Anna (1500) – Ben" })).toBeInTheDocument();
  expect(screen.getByText(/Club night · .* · \* · C40 King's Knight Opening/)).toBeInTheDocument();
  expect(screen.getByText("Club games")).toBeInTheDocument();
  expect(board("Starting position")).toBeInTheDocument();
  expect(screen.getByText("A short game")).toBeInTheDocument();
});

test("clicking a move shows its position", async () => {
  openGame(aGame());
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "Nf3!" }));

  expect(board("Position after 2. Nf3")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Nf3!" })).toHaveAttribute("aria-current", "step");
});

test("the arrow keys and Home and End step through the game", async () => {
  openGame(aGame());
  await screen.findByRole("img", { name: "Starting position" });
  const user = userEvent.setup();

  await user.keyboard("{ArrowRight}{ArrowRight}");
  expect(board("Position after 1… e5")).toBeInTheDocument();

  await user.keyboard("{ArrowLeft}");
  expect(board("Position after 1. e4")).toBeInTheDocument();

  await user.keyboard("{End}");
  expect(board("Position after 2. Nf3")).toBeInTheDocument();

  await user.keyboard("{Home}");
  expect(board("Starting position")).toBeInTheDocument();
});

test("a variation's moves are shown and followed", async () => {
  openGame(aGame());
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "c5" }));
  expect(board("Position after 1… c5")).toBeInTheDocument();
  expect(screen.getByText("The Sicilian")).toBeInTheDocument();

  await user.keyboard("{ArrowRight}");

  // The variation's own Nf3, not the main line's.
  expect(board("Position after 2. Nf3")).toBeInTheDocument();
  const variationNf3 = screen.getByRole("button", { name: "Nf3" });
  expect(variationNf3).toHaveAttribute("aria-current", "step");
});

test("the user's side is at the bottom, and the board can be flipped", async () => {
  openGame(aGame({ user_color: "black" }));
  const user = userEvent.setup();
  await screen.findByRole("img", { name: "Starting position" });
  expect(board("Starting position")).toHaveClass("orientation-black");

  await user.click(screen.getByRole("button", { name: "Flip the board" }));
  expect(board("Starting position")).toHaveClass("orientation-white");

  await user.keyboard("f");
  expect(board("Starting position")).toHaveClass("orientation-black");
});

test("copies the position's FEN", async () => {
  openGame(aGame());
  // userEvent.setup() gives the page a clipboard that the test can read back.
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "e4" }));
  await user.click(screen.getByRole("button", { name: "Copy FEN" }));

  expect(await screen.findByRole("status")).toHaveTextContent("FEN copied.");
  expect(await navigator.clipboard.readText()).toBe(
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
  );
});

test("the PGN can be downloaded", async () => {
  openGame(aGame());

  const link = await screen.findByRole("link", { name: "Download PGN" });

  expect(link).toHaveAttribute("href", "/api/v1/games/7/pgn");
});

test("a game that isn't there", async () => {
  openGame(null);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This game doesn't exist, or it isn't yours.",
  );
});

test("moves that can't be read show the PGN text instead", async () => {
  openGame(aGame({ pgn: '[FEN "not a position"]\n\n1. e4 *' }));

  expect(await screen.findByRole("alert")).toHaveTextContent("couldn't be read");
  expect(screen.getByText(/not a position/)).toBeInTheDocument();
});

test("the moves read as in a chess book", async () => {
  openGame(aGame());

  const moves = await screen.findByRole("group", { name: "Moves" });

  // Black's move gets its number where a line starts, and again after a variation. Pieces
  // are figurines, but each move is named in letters for screen readers.
  expect(moves.textContent.replace(/\s+/g, " ").trim()).toBe(
    "A short game1.e4(1.d4d5)1…e5(1…c5The Sicilian2.♘f3)2.♘f3!",
  );
  expect(screen.getByRole("button", { name: "Nf3!" })).toHaveTextContent("♘f3!");
});

test("moves can be written with letters instead, and the browser remembers it", async () => {
  openGame(aGame());
  const user = userEvent.setup();
  const figurines = await screen.findByRole("switch", { name: "Figurines (♘f3)" });
  expect(figurines).toBeChecked();

  await user.click(figurines);

  expect(figurines).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Nf3!" })).toHaveTextContent(/^Nf3!$/);

  // Another visit, in the same browser.
  cleanup();
  openGame(aGame());
  expect(await screen.findByRole("switch", { name: "Figurines (♘f3)" })).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Nf3!" })).toHaveTextContent(/^Nf3!$/);
});
