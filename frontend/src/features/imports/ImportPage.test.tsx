import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import { answerUploads } from "../../test/uploads";
import type { User } from "../auth";
import { settingsQuery } from "../settings";
import type { Import } from "./imports";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

function anImport(fields: Partial<Import> = {}): Import {
  return {
    id: 1,
    file_name: "club.pgn",
    status: "done",
    file_size: 1000,
    bytes_read: 1000,
    games_imported: 1045,
    games_duplicate: 3,
    games_failed: 0,
    errors: [],
    created_at: "2026-10-22T12:00:00Z",
    started_at: "2026-10-22T12:00:01Z",
    finished_at: "2026-10-22T12:00:05Z",
    ...fields,
  };
}

/** The simulated imports list answers with `pages`, one after another, then the last forever. */
function simulateImports(...pages: Import[][]) {
  let call = 0;
  server.use(
    http.get("*/api/v1/games/imports", () => {
      const items = pages[Math.min(call, pages.length - 1)] ?? [];
      call += 1;
      return HttpResponse.json({ items, total: items.length });
    }),
  );
}

function openImportPage({ playerNames = ["Alice"] } = {}) {
  simulateAuth(alice, { loggedIn: true });
  server.use(http.get("*/api/v1/settings", () => HttpResponse.json({ player_names: playerNames })));
  return renderApp("/import");
}

async function chooseFile(file: File) {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) {
    throw new Error("no file input on the page");
  }
  // applyAccept: false, as when someone picks "All files" in the browser's file dialog.
  await userEvent.setup({ applyAccept: false }).upload(input, file);
}

test("shows the imports with their results", async () => {
  simulateImports([anImport()]);
  openImportPage();

  const item = await screen.findByRole("listitem");

  expect(within(item).getByText("club.pgn")).toBeInTheDocument();
  expect(within(item).getByText("Done")).toBeInTheDocument();
  const imported = new Intl.NumberFormat().format(1045);
  expect(item).toHaveTextContent(`Imported: ${imported} · Already there: 3 · Unreadable: 0`);
  expect(within(item).queryByRole("progressbar")).not.toBeInTheDocument();
});

test("says so when there are no imports yet", async () => {
  simulateImports([]);
  openImportPage();

  expect(await screen.findByText("No imports yet.")).toBeInTheDocument();
});

test("a running import shows its progress and refreshes until it is done", async () => {
  const running = anImport({ status: "running", bytes_read: 400, games_imported: 500 });
  simulateImports([running], [anImport()]);
  openImportPage();

  const progress = await screen.findByRole("progressbar", { name: "Progress of club.pgn" });
  expect(progress).toHaveAttribute("aria-valuenow", "40");

  expect(await screen.findByText("Done", {}, { timeout: 3000 })).toBeInTheDocument();
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
});

test("choosing a file uploads it and shows the new import", async () => {
  simulateImports([], [anImport({ status: "queued", games_imported: 0 })]);
  const uploads = answerUploads(() =>
    HttpResponse.json(anImport({ status: "queued" }), { status: 202 }),
  );
  openImportPage();
  await screen.findByText("No imports yet.");

  await chooseFile(new File(["1. e4 e5 *"], "club.pgn"));

  expect(await screen.findByText("Waiting to start")).toBeInTheDocument();
  expect(uploads).toEqual([{ url: "/api/v1/games/imports", fields: ["file"] }]);
});

test("other files are refused before uploading them", async () => {
  simulateImports([]);
  const uploads = answerUploads(() => HttpResponse.json(anImport(), { status: 202 }));
  openImportPage();
  await screen.findByText("No imports yet.");

  await chooseFile(new File(["PK"], "games.zip"));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Only PGN files (.pgn) can be imported.",
  );
  expect(uploads).toEqual([]);
});

test("a file over the server's limit gets a message", async () => {
  simulateImports([]);
  answerUploads(() => new HttpResponse(null, { status: 413 }));
  openImportPage();
  await screen.findByText("No imports yet.");

  await chooseFile(new File(["1. e4 *"], "huge.pgn"));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This file is larger than the server accepts.",
  );
});

test("problems are listed on request", async () => {
  simulateImports([
    anImport({
      games_failed: 1,
      errors: [{ line: 25, reason: "illegal san: 'Qxf8'" }],
    }),
  ]);
  openImportPage();

  const toggle = await screen.findByRole("button", { name: "Problems (1)" });
  expect(screen.queryByText("Line 25: illegal san: 'Qxf8'")).not.toBeVisible();

  await userEvent.setup().click(toggle);

  expect(screen.getByText("Line 25: illegal san: 'Qxf8'")).toBeVisible();
});

test("the header leads to the import page", async () => {
  simulateImports([]);
  simulateAuth(alice, { loggedIn: true });
  renderApp("/");

  const link = await screen.findByRole("link", { name: "Import" });
  await userEvent.setup().click(link);

  expect(await screen.findByRole("heading", { name: "Import games" })).toBeInTheDocument();
  expect(link).toHaveAttribute("aria-current", "page");
});

test("a finished import links to its games", async () => {
  simulateImports([anImport({ id: 4 }), anImport({ id: 5, status: "running" })]);
  openImportPage();

  const links = await screen.findAllByRole("link", { name: "Show these games" });

  expect(links.map((link) => link.getAttribute("href"))).toEqual(["/games?import_run=4"]);
});

test("asks for the player names while there are none", async () => {
  simulateImports([]);
  openImportPage({ playerNames: [] });

  const link = await screen.findByRole("link", { name: "Add them in Settings" });
  expect(link).toHaveAttribute("href", "/settings");
});

test("says nothing about player names once there are some", async () => {
  simulateImports([]);
  const { queryClient } = openImportPage();

  await waitFor(() => {
    expect(queryClient.getQueryData(settingsQuery.queryKey)).toBeDefined();
  });
  expect(screen.queryByRole("link", { name: "Add them in Settings" })).not.toBeInTheDocument();
});
