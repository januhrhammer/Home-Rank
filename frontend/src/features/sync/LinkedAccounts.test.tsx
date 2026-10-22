import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";
import type { LinkedAccount, NewAccount, SyncRun } from "./sync";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

function aRun(fields: Partial<SyncRun> = {}): SyncRun {
  return {
    id: 1,
    status: "done",
    games_imported: 12,
    games_duplicate: 3,
    games_failed: 1,
    errors: [],
    created_at: "2026-10-22T12:00:00Z",
    started_at: "2026-10-22T12:00:01Z",
    finished_at: "2026-10-22T12:00:05Z",
    ...fields,
  };
}

function anAccount(fields: Partial<LinkedAccount> = {}): LinkedAccount {
  return {
    id: 1,
    platform: "lichess",
    username: "alice64",
    enabled: true,
    synced_until: null,
    created_at: "2026-10-22T11:00:00Z",
    last_run: null,
    ...fields,
  };
}

/**
 * A simulated sync API that keeps the accounts like the server does. New accounts and
 * "sync now" get a queued sync. Returns what it was asked to do.
 */
function simulateSync(initial: LinkedAccount[]) {
  let accounts = initial;
  const requests: string[] = [];
  const queued = aRun({ status: "queued", games_imported: 0, finished_at: null });
  server.use(
    http.get("*/api/v1/sync/accounts", () =>
      HttpResponse.json({ items: accounts, total: accounts.length }),
    ),
    http.post("*/api/v1/sync/accounts", async ({ request }) => {
      const body = (await request.json()) as NewAccount;
      requests.push(`link ${body.platform} ${body.username}`);
      const account = anAccount({ id: accounts.length + 1, ...body, last_run: queued });
      accounts = [...accounts, account];
      return HttpResponse.json(account, { status: 201 });
    }),
    http.post("*/api/v1/sync/accounts/:id/sync", ({ params }) => {
      requests.push(`sync ${String(params.id)}`);
      accounts = accounts.map((a) => (String(a.id) === params.id ? { ...a, last_run: queued } : a));
      return HttpResponse.json(queued, { status: 202 });
    }),
    http.patch("*/api/v1/sync/accounts/:id", async ({ params, request }) => {
      const { enabled } = (await request.json()) as { enabled: boolean };
      requests.push(`enabled ${String(params.id)} ${String(enabled)}`);
      accounts = accounts.map((a) => (String(a.id) === params.id ? { ...a, enabled } : a));
      return HttpResponse.json(accounts.find((a) => String(a.id) === params.id));
    }),
    http.delete("*/api/v1/sync/accounts/:id", ({ params }) => {
      requests.push(`unlink ${String(params.id)}`);
      accounts = accounts.filter((a) => String(a.id) !== params.id);
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return requests;
}

function openImportPage() {
  simulateAuth(alice, { loggedIn: true });
  server.use(
    http.get("*/api/v1/settings", () => HttpResponse.json({ player_names: ["alice64"] })),
    http.get("*/api/v1/games/imports", () => HttpResponse.json({ items: [], total: 0 })),
  );
  renderApp("/import");
}

async function accountItem(name: string) {
  return screen.findByRole("listitem", { name });
}

test("shows each account with how its last sync went", async () => {
  simulateSync([
    anAccount({ last_run: aRun() }),
    anAccount({ id: 2, platform: "chesscom", username: "Alice_C" }),
  ]);
  openImportPage();

  const lichess = await accountItem("Lichess account alice64");
  expect(lichess).toHaveTextContent("Synced");
  expect(lichess).toHaveTextContent("New: 12 · Already there: 3 · Unreadable: 1");
  expect(within(lichess).getByRole("link", { name: "Show games from Lichess" })).toHaveAttribute(
    "href",
    "/games?source=lichess",
  );
  expect(within(lichess).getByRole("switch", { name: "Sync automatically" })).toBeChecked();
  const chesscom = await accountItem("Chess.com account Alice_C");
  expect(chesscom).toHaveTextContent("Not synced yet");
});

test("a failed sync shows why it stopped", async () => {
  const reason = 'There is no player called "alice64".';
  simulateSync([
    anAccount({ last_run: aRun({ status: "failed", errors: [{ game: null, reason }] }) }),
  ]);
  openImportPage();

  const item = await accountItem("Lichess account alice64");

  expect(item).toHaveTextContent("Sync stopped");
  expect(item).toHaveTextContent(reason);
});

test("links an account, which starts syncing", async () => {
  const requests = simulateSync([]);
  openImportPage();
  const user = userEvent.setup();

  expect(await screen.findByText("No accounts linked yet.")).toBeInTheDocument();
  await user.click(screen.getByRole("radio", { name: "Chess.com" }));
  await user.type(screen.getByRole("textbox", { name: "Username" }), "Alice_C");
  await user.click(screen.getByRole("button", { name: "Link account" }));

  const item = await accountItem("Chess.com account Alice_C");
  expect(requests).toEqual(["link chesscom Alice_C"]);
  expect(item).toHaveTextContent("Waiting to sync");
  expect(within(item).getByRole("progressbar", { name: "Syncing Alice_C" })).toBeInTheDocument();
  expect(within(item).getByRole("button", { name: "Sync now" })).toBeDisabled();
  expect(screen.getByRole("textbox", { name: "Username" })).toHaveValue("");
});

test("linking an account twice says so", async () => {
  simulateSync([]);
  server.use(http.post("*/api/v1/sync/accounts", () => new HttpResponse(null, { status: 409 })));
  openImportPage();
  const user = userEvent.setup();

  await user.type(await screen.findByRole("textbox", { name: "Username" }), "alice64");
  await user.click(screen.getByRole("button", { name: "Link account" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("already linked this account");
});

test("an impossible username says what is allowed", async () => {
  simulateSync([]);
  server.use(http.post("*/api/v1/sync/accounts", () => new HttpResponse(null, { status: 422 })));
  openImportPage();
  const user = userEvent.setup();

  await user.type(await screen.findByRole("textbox", { name: "Username" }), "alice 64");
  await user.click(screen.getByRole("button", { name: "Link account" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("2 to 50 letters");
});

test("syncs an account now", async () => {
  const requests = simulateSync([anAccount({ last_run: aRun() })]);
  openImportPage();
  const user = userEvent.setup();
  const item = await accountItem("Lichess account alice64");

  await user.click(within(item).getByRole("button", { name: "Sync now" }));

  await waitFor(() => {
    expect(item).toHaveTextContent("Waiting to sync");
  });
  expect(requests).toEqual(["sync 1"]);
});

test("shows how many games a running sync has stored", async () => {
  simulateSync([anAccount({ last_run: aRun({ status: "running", games_imported: 250 }) })]);
  openImportPage();

  const item = await accountItem("Lichess account alice64");

  expect(item).toHaveTextContent("Syncing… 250 new games so far");
});

test("turns the automatic sync off", async () => {
  const requests = simulateSync([anAccount()]);
  openImportPage();
  const user = userEvent.setup();
  const item = await accountItem("Lichess account alice64");

  await user.click(within(item).getByRole("switch", { name: "Sync automatically" }));

  await waitFor(() => {
    expect(within(item).getByRole("switch", { name: "Sync automatically" })).not.toBeChecked();
  });
  expect(requests).toEqual(["enabled 1 false"]);
});

test("unlinks an account", async () => {
  const requests = simulateSync([anAccount()]);
  openImportPage();
  const user = userEvent.setup();
  const item = await accountItem("Lichess account alice64");

  await user.click(within(item).getByRole("button", { name: "Unlink" }));

  expect(await screen.findByText("No accounts linked yet.")).toBeInTheDocument();
  expect(requests).toEqual(["unlink 1"]);
});

test("accounts that can't be loaded say so", async () => {
  server.use(http.get("*/api/v1/sync/accounts", () => new HttpResponse(null, { status: 500 })));
  openImportPage();

  expect(await screen.findByRole("alert")).toHaveTextContent("couldn't be loaded");
});

test("follows a sync until it is done", async () => {
  const pages = [
    [anAccount({ last_run: aRun({ status: "running", games_imported: 5 }) })],
    [anAccount({ last_run: aRun({ games_imported: 40 }) })],
  ];
  let call = 0;
  server.use(
    http.get("*/api/v1/sync/accounts", () => {
      const items = pages[Math.min(call, pages.length - 1)] ?? [];
      call += 1;
      return HttpResponse.json({ items, total: items.length });
    }),
  );
  openImportPage();

  const item = await accountItem("Lichess account alice64");
  expect(item).toHaveTextContent("5 new games so far");

  await waitFor(
    () => {
      expect(item).toHaveTextContent("New: 40");
    },
    { timeout: 4000 },
  );
});
