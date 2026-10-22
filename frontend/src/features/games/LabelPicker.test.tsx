import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";
import type { Game, NamedRef } from "./games";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

const GAME: Game = {
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
  user_color: "",
  ply_count: 1,
  source: "pgn",
  imported_at: "2026-10-22T12:00:00Z",
  tags: [],
  pgn: "1. e4 *\n",
  import_run_id: null,
  collections: [],
};

/**
 * A simulated API that remembers the user's tags and which of them game 7 has, so the page
 * shows each change once it has reloaded the game.
 */
function simulateTags(existing: NamedRef[], onGame: number[]) {
  const tags = [...existing];
  const gameTags = new Set(onGame);
  const requests: string[] = [];
  server.use(
    http.get("*/api/v1/games/7", () =>
      HttpResponse.json({ ...GAME, tags: tags.filter((tag) => gameTags.has(tag.id)) }),
    ),
    http.get("*/api/v1/tags", () =>
      HttpResponse.json({
        items: tags.map((tag) => ({ ...tag, game_count: 0 })),
        total: tags.length,
      }),
    ),
    http.get("*/api/v1/collections", () => HttpResponse.json({ items: [], total: 0 })),
    http.post("*/api/v1/tags", async ({ request }) => {
      const { name } = (await request.json()) as { name: string };
      const tag = { id: 100 + tags.length, name };
      tags.push(tag);
      requests.push(`create ${name}`);
      return HttpResponse.json({ ...tag, game_count: 0 }, { status: 201 });
    }),
    http.post("*/api/v1/tags/:tagId/games", async ({ params, request }) => {
      const { game_ids } = (await request.json()) as { game_ids: number[] };
      gameTags.add(Number(params.tagId));
      requests.push(`add ${String(params.tagId)} to ${game_ids.join(",")}`);
      return HttpResponse.json({ id: Number(params.tagId), name: "", game_count: 1 });
    }),
    http.delete("*/api/v1/tags/:tagId/games", ({ params, request }) => {
      const gameIds = new URL(request.url).searchParams.getAll("game_ids");
      gameTags.delete(Number(params.tagId));
      requests.push(`remove ${String(params.tagId)} from ${gameIds.join(",")}`);
      return HttpResponse.json({ id: Number(params.tagId), name: "", game_count: 0 });
    }),
  );
  simulateAuth(alice, { loggedIn: true });
  renderApp("/games/7");
  return requests;
}

function tagChips() {
  const group = screen.getByRole("grid", { name: "Tags" });
  return within(group)
    .queryAllByRole("row")
    .map((row) => row.textContent.replace("×", ""));
}

test("shows the game's tags, and removes one", async () => {
  const requests = simulateTags(
    [
      { id: 1, name: "Blunder" },
      { id: 2, name: "Endgame" },
    ],
    [1, 2],
  );
  const user = userEvent.setup();
  await screen.findByRole("button", { name: "Remove Blunder" });
  expect(tagChips()).toEqual(["Blunder", "Endgame"]);

  await user.click(screen.getByRole("button", { name: "Remove Blunder" }));

  await waitFor(() => {
    expect(tagChips()).toEqual(["Endgame"]);
  });
  expect(requests).toEqual(["remove 1 from 7"]);
});

test("adds one of the user's tags", async () => {
  const requests = simulateTags(
    [
      { id: 1, name: "Blunder" },
      { id: 2, name: "Brilliant" },
    ],
    [1],
  );
  const user = userEvent.setup();

  await user.type(await screen.findByRole("combobox", { name: "Add a tag" }), "bri");
  // Tags the game already has aren't suggested.
  expect(screen.queryByRole("option", { name: "Blunder" })).not.toBeInTheDocument();
  await user.click(await screen.findByRole("option", { name: "Brilliant" }));

  await waitFor(() => {
    expect(tagChips()).toEqual(["Blunder", "Brilliant"]);
  });
  expect(requests).toEqual(["add 2 to 7"]);
  expect(screen.getByRole("combobox", { name: "Add a tag" })).toHaveValue("");
});

test("creates a new tag from the typed name", async () => {
  const requests = simulateTags([], []);
  const user = userEvent.setup();

  await user.type(await screen.findByRole("combobox", { name: "Add a tag" }), "Queen sacrifice");
  await user.click(await screen.findByRole("option", { name: "Create “Queen sacrifice”" }));

  await waitFor(() => {
    expect(tagChips()).toEqual(["Queen sacrifice"]);
  });
  expect(requests).toEqual(["create Queen sacrifice", "add 100 to 7"]);
});

test("a name that exists in other capitals is suggested, not created again", async () => {
  simulateTags([{ id: 1, name: "Blitz" }], []);
  const user = userEvent.setup();

  await user.type(await screen.findByRole("combobox", { name: "Add a tag" }), "blitz");

  expect(await screen.findByRole("option", { name: "Blitz" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: /Create/ })).not.toBeInTheDocument();
});

test("typing a name doesn't trigger the viewer's keys", async () => {
  simulateTags([], []);
  const user = userEvent.setup();
  const field = await screen.findByRole("combobox", { name: "Add a tag" });

  // F flips the board and → steps forward, but not while typing in a field.
  await user.type(field, "f{ArrowRight}");
  expect(field).toHaveValue("f");
  // hidden: the open suggestions hide the rest of the page from screen readers meanwhile.
  const board = screen.getByRole("img", { name: "Starting position", hidden: true });
  expect(board).toHaveClass("orientation-white");
});
