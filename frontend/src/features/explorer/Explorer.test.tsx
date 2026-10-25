import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";
import type { Game } from "../games/games";
import type { ExplorerData, ReferenceDatabase, ReferenceGame } from "./explorer";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };
const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

const MASTERS: ReferenceDatabase = {
  id: 3,
  name: "Masters",
  description: "Over the board, 1850-2026",
  depth: 30,
  status: "ready",
  game_count: 12345,
  imported_at: "2026-10-23T08:00:00Z",
};

function explorer(moves: [string, string, number][]): ExplorerData {
  return {
    games: moves.reduce((sum, [, , n]) => sum + n, 0),
    filtered: true,
    opening: null,
    moves: moves.map(([uci, san, games]) => ({
      uci,
      san,
      games,
      white: games,
      draws: 0,
      black: 0,
      average_rating: 1800,
      last_played: "2026-02-01",
    })),
  };
}

function aGame(): Game {
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
    ply_count: 2,
    source: "pgn",
    imported_at: "2026-10-22T12:00:00Z",
    tags: [],
    pgn: '[White "Anna"]\n[Black "Ben"]\n[Result "*"]\n\n1. e4 e5 *\n',
    import_run_id: null,
    collections: [],
  };
}

function aReferenceGame(): ReferenceGame {
  return {
    id: 1,
    white: "Morphy, Paul",
    black: "Duke Karl",
    white_elo: 2690,
    black_elo: null,
    result: "1-0",
    date_pgn: "1858.??.??",
    event: "Paris",
    site: "",
    eco: "C41",
    opening: "Philidor Defense",
    ply_count: 2,
    pgn: '[White "Morphy, Paul"]\n[Black "Duke Karl"]\n[Result "1-0"]\n\n1. e4 e5 1-0\n',
  };
}

/** The explorer and reference API, answering "my games" and Masters differently. */
function simulateExplorer() {
  const requests: string[] = [];
  server.use(
    http.get("*/api/v1/reference/databases", () => HttpResponse.json([MASTERS])),
    http.get("*/api/v1/explorer/my", ({ request }) => {
      const fen = new URL(request.url).searchParams.get("fen") ?? "";
      requests.push(fen);
      // After 1. e4 the position has a name in Lichess's list.
      const opening = fen.startsWith("rnbqkbnr/pppppppp/8/8/4P3")
        ? { eco: "B00", name: "King's Pawn Game" }
        : null;
      return HttpResponse.json({ ...explorer([["e2e4", "e4", 5]]), opening });
    }),
    http.get("*/api/v1/explorer/reference/:id", () =>
      HttpResponse.json(
        explorer([
          ["d2d4", "d4", 900],
          ["e2e4", "e4", 800],
        ]),
      ),
    ),
    http.get("*/api/v1/explorer/search/my", () =>
      HttpResponse.json({ items: [{ ...aGame(), ply: 0 }], total: 1 }),
    ),
    http.get("*/api/v1/explorer/search/reference/:id", () =>
      HttpResponse.json({ items: [{ ...aReferenceGame(), ply: 0 }], total: 1, too_common: false }),
    ),
    http.get("*/api/v1/reference/databases/:id/games", () =>
      HttpResponse.json({ items: [aReferenceGame()], total: 1 }),
    ),
    http.get("*/api/v1/reference/databases/:id/games/:gameId", () =>
      HttpResponse.json(aReferenceGame()),
    ),
    http.post("*/api/v1/reference/databases/:id/games/:gameId/copy", () =>
      HttpResponse.json({ game_id: 7, created: true }, { status: 201 }),
    ),
    http.get("*/api/v1/games/:gameId", () => HttpResponse.json(aGame())),
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
  return requests;
}

function open(path: string) {
  simulateAuth(alice, { loggedIn: true });
  renderApp(path);
}

test("the viewer's explorer shows my moves and steps into the game", async () => {
  simulateExplorer();
  open("/games/7");
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "Opening explorer" }));
  const table = await screen.findByRole("table");
  expect(within(table).getByRole("row", { name: /e4/ })).toHaveTextContent("5");

  await user.click(within(table).getByRole("button", { name: "e4" }));

  expect(await screen.findByRole("img", { name: "Position after 1. e4" })).toBeInTheDocument();
  expect(await screen.findByText("King's Pawn Game")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Find games with this position" })).toHaveAttribute(
    "href",
    `/search?${new URLSearchParams({ fen: "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1" }).toString()}`,
  );
});

test("the explorer can show a reference database instead", async () => {
  simulateExplorer();
  open("/search");
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: /Games from/ }));
  await user.click(screen.getByRole("option", { name: "Masters" }));

  const rows = await screen.findAllByRole("row");
  expect(rows[1]).toHaveTextContent("d4");
  expect(await screen.findByRole("link", { name: "Morphy, Paul – Duke Karl" })).toHaveAttribute(
    "href",
    "/reference/3/games/1",
  );
});

test("the chosen database is kept, for the explorer everywhere", async () => {
  simulateExplorer();
  open("/search");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /Games from/ }));
  await user.click(screen.getByRole("option", { name: "Masters" }));
  await screen.findByRole("link", { name: "Morphy, Paul – Duke Karl" });

  // Another page, another time: the viewer's explorer starts with Masters.
  cleanup();
  open("/games/7");
  await user.click(await screen.findByRole("button", { name: "Opening explorer" }));

  expect(await screen.findByRole("button", { name: /Masters.*Games from/ })).toBeInTheDocument();
  const rows = await screen.findAllByRole("row");
  expect(rows[1]).toHaveTextContent("d4");
});

test("a database no longer there means my games again", async () => {
  localStorage.setItem("home-rank.explorer-source", "99");
  simulateExplorer();
  open("/search");

  expect(await screen.findByRole("button", { name: /My games.*Games from/ })).toBeInTheDocument();
});

test("the search page finds my games reaching the position", async () => {
  const requests = simulateExplorer();
  open(`/search?${new URLSearchParams({ fen: START }).toString()}`);

  expect(await screen.findByRole("link", { name: "Anna – Ben" })).toHaveAttribute(
    "href",
    "/games/7",
  );
  expect(requests).toContain(START);
});

test("a typed FEN sets the board, and impossible positions are explained", async () => {
  simulateExplorer();
  open("/search");
  const user = userEvent.setup();
  const field = await screen.findByRole("textbox", { name: "FEN" });

  await user.clear(field);
  await user.type(field, "8/8/8/8/8/8/8/8 w - - 0 1");

  expect(await screen.findByRole("alert")).toHaveTextContent("isn't a legal position");
});

test("browses a reference database and copies a game", async () => {
  simulateExplorer();
  open("/reference");
  const user = userEvent.setup();

  expect(await screen.findByText(/Over the board, 1850-2026/)).toBeInTheDocument();
  expect(await screen.findByRole("row", { name: /Morphy, Paul/ })).toHaveTextContent(
    "C41 Philidor Defense",
  );
  await user.click(await screen.findByRole("link", { name: "Morphy, Paul" }));
  expect(await screen.findByRole("heading", { name: "Morphy, Paul – Duke Karl" })).toBeVisible();
  // Live analysis without copying the game first; it starts switched off.
  expect(screen.getByRole("switch", { name: "Live analysis" })).not.toBeChecked();
  await user.click(screen.getByRole("button", { name: "Copy to my games" }));

  expect(await screen.findByRole("heading", { name: /Anna – Ben/ })).toBeVisible();
});
