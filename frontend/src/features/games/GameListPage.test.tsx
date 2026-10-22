import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";
import type { GameListItem } from "./games";
import { formatGameDate } from "./GameTable";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

function aGame(fields: Partial<GameListItem> = {}): GameListItem {
  return {
    id: 1,
    white: "Uhrhammer, Jan",
    black: "Carlsen, Magnus",
    white_elo: 1850,
    black_elo: 2830,
    result: "1/2-1/2",
    date: "2024-03-05",
    date_pgn: "2024.03.05",
    event: "Club championship",
    site: "",
    eco: "B90",
    opening: "Sicilian Defense: Najdorf Variation",
    time_control: "180+2",
    time_class: "blitz",
    user_color: "white",
    ply_count: 60,
    source: "pgn",
    imported_at: "2026-10-22T12:00:00Z",
    tags: [{ id: 3, name: "Brilliant" }],
    ...fields,
  };
}

/** Answers the game list with `games` (and `total`), and records each request's query. */
function simulateGames(games: GameListItem[], total = games.length) {
  const queries: URLSearchParams[] = [];
  server.use(
    http.get("*/api/v1/games", ({ request }) => {
      queries.push(new URL(request.url).searchParams);
      return HttpResponse.json({ items: games, total });
    }),
    http.get("*/api/v1/tags", () =>
      HttpResponse.json({ items: [{ id: 3, name: "Brilliant", game_count: 1 }], total: 1 }),
    ),
    http.get("*/api/v1/collections", () => HttpResponse.json({ items: [], total: 0 })),
  );
  return {
    /** The query of the latest request, e.g. latest().get("outcome"). */
    latest: () => queries.at(-1) ?? new URLSearchParams(),
    /** The values a parameter had in all requests so far. */
    valuesOf: (name: string) => queries.map((query) => query.get(name)),
  };
}

function openGames(address = "/games") {
  simulateAuth(alice, { loggedIn: true });
  renderApp(address);
}

test("lists the games in a table", async () => {
  simulateGames([aGame()]);
  openGames();

  const row = (await screen.findAllByRole("row"))[1];
  if (row === undefined) {
    throw new Error("no game row");
  }

  // The cells in order; the White column is the row's header.
  const cells = [...row.querySelectorAll('[role="gridcell"], [role="rowheader"]')];
  expect(cells.map((cell) => cell.textContent)).toEqual([
    formatGameDate("2024.03.05"),
    "Uhrhammer, Jan 1850",
    "Carlsen, Magnus 2830",
    "½-½",
    "B90 Sicilian Defense: Najdorf Variation",
    "Blitz",
    "Club championshipBrilliant",
  ]);
  // The user's own side is emphasised.
  expect(within(row).getByText("Uhrhammer, Jan").tagName).toBe("STRONG");
});

test("shows only what is known of a date", () => {
  expect(formatGameDate("1960.??.??")).toBe("1960");
  expect(formatGameDate("????.??.??")).toBe("");
  expect(formatGameDate("1960.05.??")).toBe(
    new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(
      new Date(1960, 4, 1),
    ),
  );
});

test("the address holds the filters, the sort and the page", async () => {
  const api = simulateGames([aGame()], 120);
  openGames("/games?outcome=loss&time_class=blitz&sort=white&page=2");

  await screen.findByRole("grid");

  const query = api.latest();
  expect(query.get("outcome")).toBe("loss");
  expect(query.get("time_class")).toBe("blitz");
  expect(query.get("sort")).toBe("white");
  expect([query.get("limit"), query.get("offset")]).toEqual(["50", "50"]);
  expect(screen.getByText("51–100 of 120")).toBeInTheDocument();
});

test("invalid values in the address are ignored", async () => {
  const api = simulateGames([aGame()]);
  openGames("/games?color=green&page=x&sort=pgn");

  await screen.findByRole("grid");

  expect(api.latest().get("color")).toBeNull();
  expect(api.latest().get("offset")).toBe("0");
  expect(api.latest().get("sort")).toBe("-date");
});

test("choosing a filter asks for matching games, from the first page", async () => {
  const api = simulateGames([aGame()], 120);
  openGames("/games?page=2");
  await screen.findByRole("grid");
  const user = userEvent.setup();

  await user.click(screen.getByRole("button", { name: /Your side/ }));
  await user.click(await screen.findByRole("option", { name: "Black" }));

  await waitFor(() => {
    expect(api.latest().get("color")).toBe("black");
  });
  expect(api.latest().get("offset")).toBe("0");
});

test("typing a player's name applies once the typing pauses", async () => {
  const api = simulateGames([aGame()]);
  openGames();
  await screen.findByRole("grid");

  await userEvent.setup().type(screen.getByRole("searchbox", { name: "Player" }), "carlsen");

  await waitFor(() => {
    expect(api.latest().get("player")).toBe("carlsen");
  });
  // Not once per keystroke: no request for "c", "ca", …
  expect(api.valuesOf("player").filter((value) => value !== null)).toEqual(["carlsen"]);
});

test("clicking a column sorts by it, clicking again reverses", async () => {
  const api = simulateGames([aGame()]);
  openGames();
  const user = userEvent.setup();
  const column = await screen.findByRole("columnheader", { name: "White" });

  await user.click(column);
  await waitFor(() => {
    expect(api.latest().get("sort")).toBe("white");
  });

  await user.click(column);
  await waitFor(() => {
    expect(api.latest().get("sort")).toBe("-white");
  });
});

test("pages through the games", async () => {
  const api = simulateGames([aGame()], 120);
  openGames();
  const user = userEvent.setup();
  await screen.findByText("1–50 of 120");
  expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

  await user.click(screen.getByRole("button", { name: "Next" }));

  await waitFor(() => {
    expect(api.latest().get("offset")).toBe("50");
  });
  expect(await screen.findByText("51–100 of 120")).toBeInTheDocument();
});

test("without games, it points to the import page", async () => {
  simulateGames([]);
  openGames();

  expect(await screen.findByText(/No games yet/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Import your games" })).toHaveAttribute(
    "href",
    "/import",
  );
});

test("when no game matches, the filters can be cleared", async () => {
  simulateGames([]);
  openGames("/games?outcome=win");

  expect(await screen.findByText(/No games match these filters/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Clear filters" })).toHaveAttribute("href", "/games");
});

test("the header leads to the games", async () => {
  simulateGames([aGame()]);
  simulateAuth(alice, { loggedIn: true });
  renderApp("/");

  await userEvent.setup().click(await screen.findByRole("link", { name: "Games" }));

  expect(await screen.findByRole("heading", { name: "Your games" })).toBeInTheDocument();
});
