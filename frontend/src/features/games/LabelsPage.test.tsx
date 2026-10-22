import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

interface Stored {
  id: number;
  name: string;
  description: string;
  game_count: number;
}

/** A simulated API that remembers the user's collections and tags, and what was asked of it. */
function simulateLabels(collections: Stored[], tags: Stored[]) {
  const store = { collections: [...collections], tags: [...tags] };
  const requests: string[] = [];
  for (const kind of ["collections", "tags"] as const) {
    server.use(
      http.get(`*/api/v1/${kind}`, () =>
        HttpResponse.json({ items: store[kind], total: store[kind].length }),
      ),
      http.post(`*/api/v1/${kind}`, async ({ request }) => {
        const body = (await request.json()) as { name: string; description?: string };
        const item = { id: 50 + store[kind].length, description: "", game_count: 0, ...body };
        store[kind].push(item);
        requests.push(`create ${kind} ${JSON.stringify(body)}`);
        return HttpResponse.json(item, { status: 201 });
      }),
      http.patch(`*/api/v1/${kind}/:id`, async ({ params, request }) => {
        const body = (await request.json()) as { name: string };
        const id = Number(params.id);
        if (store[kind].some((item) => item.id !== id && item.name === body.name)) {
          return new HttpResponse(null, { status: 409 });
        }
        store[kind] = store[kind].map((item) => (item.id === id ? { ...item, ...body } : item));
        requests.push(`update ${kind} ${String(id)} ${JSON.stringify(body)}`);
        return HttpResponse.json(store[kind].find((item) => item.id === id));
      }),
      http.delete(`*/api/v1/${kind}/:id`, ({ params }) => {
        store[kind] = store[kind].filter((item) => item.id !== Number(params.id));
        requests.push(`delete ${kind} ${String(params.id)}`);
        return new HttpResponse(null, { status: 204 });
      }),
    );
  }
  simulateAuth(alice, { loggedIn: true });
  renderApp("/labels");
  return requests;
}

const CLUB = { id: 1, name: "Club games", description: "Hamburg league", game_count: 12 };
const BLUNDER = { id: 2, name: "Blunder", description: "", game_count: 3 };

function section(name: "Collections" | "Tags") {
  return screen.getByRole("region", { name });
}

test("lists collections and tags with their games", async () => {
  simulateLabels([CLUB], [BLUNDER]);

  const club = await screen.findByRole("link", { name: "Club games" });

  expect(club).toHaveAttribute("href", "/games?collection=1");
  expect(within(section("Collections")).getByText("12 games")).toBeInTheDocument();
  expect(within(section("Collections")).getByText("Hamburg league")).toBeInTheDocument();
  expect(within(section("Tags")).getByRole("link", { name: "Blunder" })).toHaveAttribute(
    "href",
    "/games?tag=2",
  );
  expect(within(section("Collections")).getByRole("link", { name: "Export PGN" })).toHaveAttribute(
    "href",
    "/api/v1/games/export?collection=1",
  );
});

test("creates a collection with a description", async () => {
  const requests = simulateLabels([], []);
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "New collection" }));
  const dialog = screen.getByRole("dialog", { name: "New collection" });
  await user.type(within(dialog).getByLabelText("Name"), "  Classics ");
  await user.type(within(dialog).getByLabelText("Description"), "Games to learn from");
  await user.click(within(dialog).getByRole("button", { name: "Save" }));

  expect(await screen.findByRole("link", { name: "Classics" })).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(requests).toEqual([
    'create collections {"name":"Classics","description":"Games to learn from"}',
  ]);
});

test("renames a tag", async () => {
  const requests = simulateLabels([], [BLUNDER]);
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "Edit “Blunder”" }));
  const name = screen.getByLabelText("Name");
  await user.clear(name);
  await user.type(name, "Blunders");
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByRole("link", { name: "Blunders" })).toBeInTheDocument();
  expect(requests).toEqual(['update tags 2 {"name":"Blunders"}']);
});

test("a taken name is explained, and the dialog stays open", async () => {
  simulateLabels([], [BLUNDER, { ...BLUNDER, id: 3, name: "Endgame" }]);
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "Edit “Endgame”" }));
  const name = screen.getByLabelText("Name");
  await user.clear(name);
  await user.type(name, "Blunder");
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "You already have one called “Blunder”.",
  );
  expect(screen.getByRole("dialog")).toBeInTheDocument();
});

test("deleting asks first, and keeps the games", async () => {
  const requests = simulateLabels([CLUB], []);
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "Delete “Club games”?" }));
  const dialog = screen.getByRole("alertdialog", { name: "Delete “Club games”?" });
  expect(dialog).toHaveTextContent("its games stay in your database");

  await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(requests).toEqual([]);

  await user.click(screen.getByRole("button", { name: "Delete “Club games”?" }));
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Delete" }));

  await waitFor(() => {
    expect(screen.queryByRole("link", { name: "Club games" })).not.toBeInTheDocument();
  });
  expect(requests).toEqual(["delete collections 1"]);
});

test("explains where tags and collections come from when there are none", async () => {
  simulateLabels([], []);

  expect(await screen.findByText(/No collections yet/)).toBeInTheDocument();
  expect(screen.getByText(/No tags yet/)).toBeInTheDocument();
});
