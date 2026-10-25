import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";
import type { NewSearch, NoveltyTry, SearchDetail } from "./novelty";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

// The deep Smith-Morra position the novelty spike started from, White to play its 10th move.
const MORRA = "r1bqk2r/pp2bppp/2np1n2/4p3/2B1P3/2N2N2/PP2QPPP/R1BR2K1 w kq - 0 10";

const B4: NoveltyTry = {
  rank: 0,
  line: [],
  uci: "b2b4",
  san: "b4",
  cp: -28,
  practical: 0.64,
  best_san: "Bb5",
  best_practical: 0.57,
  reach: 1,
  refutation: [
    { san: "Bg4", uci: "c8g4", found: 0.75 },
    { san: "b5", uci: "b4b5", found: null },
    { san: "Na5", uci: "c6a5", found: 0.33 },
  ],
  reference_games: 0,
};

const ND5: NoveltyTry = {
  ...B4,
  rank: 1,
  line: ["c1e3", "e8g8"],
  uci: "c3d5",
  san: "Nd5",
  cp: 0,
  practical: 0.6,
  best_san: "h3",
  best_practical: 0.52,
  refutation: [{ san: "Nxd5", uci: "f6d5", found: 0.7 }],
  reference_games: 3,
};

function aSearch(fields: Partial<SearchDetail> = {}): SearchDetail {
  return {
    id: 7,
    start_fen: MORRA,
    start_moves: [],
    start_label: "Smith-Morra, after 9.Rd1 e5",
    side: "white",
    rating: 1800,
    rating_kind: "fide",
    elo: 1962,
    budget_cp: 150,
    limit_minutes: 60,
    status: "done",
    own_moves: 3,
    error: "",
    created_at: "2026-10-25T10:00:00Z",
    started_at: "2026-10-25T10:00:00Z",
    finished_at: "2026-10-25T11:00:00Z",
    tries: [B4, ND5],
    ...fields,
  };
}

function simulateNovelty(search: SearchDetail) {
  const received: { started: NewSearch[]; cancelled: number; deleted: number } = {
    started: [],
    cancelled: 0,
    deleted: 0,
  };
  server.use(
    http.get("*/api/v1/novelty/searches", () => HttpResponse.json({ items: [search], total: 1 })),
    http.post("*/api/v1/novelty/searches", async ({ request }) => {
      received.started.push((await request.json()) as NewSearch);
      return HttpResponse.json({ ...search, status: "queued", tries: undefined }, { status: 201 });
    }),
    http.get("*/api/v1/novelty/searches/7", () => HttpResponse.json(search)),
    http.post("*/api/v1/novelty/searches/7/cancel", () => {
      received.cancelled += 1;
      return HttpResponse.json({ ...search, status: "cancelled" });
    }),
    http.delete("*/api/v1/novelty/searches/7", () => {
      received.deleted += 1;
      return new HttpResponse(null, { status: 204 });
    }),
    http.get("*/api/v1/novelty/rating", ({ request }) => {
      const params = new URL(request.url).searchParams;
      const rating = Number(params.get("rating"));
      return HttpResponse.json({ elo: params.get("kind") === "dwz" ? rating + 250 : rating + 200 });
    }),
    http.get("*/api/v1/explorer/search/my", () => HttpResponse.json({ items: [], total: 0 })),
    http.get("*/api/v1/explorer/my", () =>
      HttpResponse.json({ games: 0, moves: [], filtered: true, opening: null }),
    ),
    http.get("*/api/v1/reference/databases", () => HttpResponse.json([])),
  );
  return received;
}

test("a search is started from a board, with the rating Maia will play at", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateNovelty(aSearch());
  renderApp("/search");
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "Find tries" }));
  const dialog = screen.getByRole("dialog");
  const rating = within(dialog).getByLabelText("Opponent's rating");
  await user.clear(rating);
  await user.type(rating, "1500");
  await user.click(within(dialog).getByText("DWZ"));
  expect(await within(dialog).findByText(/rated about 1750/)).toBeInTheDocument();
  await user.click(within(dialog).getByText("Overnight (8 hours)"));
  await user.click(within(dialog).getByRole("button", { name: "Start search" }));

  await waitFor(() => {
    expect(received.started).toHaveLength(1);
  });
  expect(received.started[0]).toMatchObject({
    side: "white",
    rating: 1500,
    rating_kind: "dwz",
    elo: null,
    budget_cp: 150,
    limit_minutes: 480,
  });
  expect(await screen.findByRole("heading", { name: "Smith-Morra, after 9.Rd1 e5" })).toBeVisible();
});

test("a search's tries show their line, chances and refutation, its hard moves marked", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateNovelty(aSearch());
  renderApp("/novelty/7");
  const user = userEvent.setup();

  expect(await screen.findByRole("status")).toHaveTextContent("Finished: 3 of your moves deep.");
  const b4 = screen.getByRole("button", { name: /^10\.b4:/ });
  expect(b4).toHaveAttribute("aria-pressed", "true");
  expect(b4).toHaveTextContent("64 % against this opponent (♗b5: 57 %) · −0.28");
  expect(screen.getByRole("img", { name: "Position before 10.b4" })).toBeInTheDocument();
  const refutation = screen.getByRole("region", { name: "The refutation" });
  // 75 % × 33 %: the opponent finds the whole refutation a quarter of the time.
  expect(refutation).toHaveTextContent("Your opponent finds all of it 25 % of the time.");
  expect(refutation).toHaveTextContent("isn't in your reference database");
  expect(
    within(refutation)
      .getAllByRole("listitem")
      .map((item) => item.textContent),
  ).toEqual(["10…♗g4found 75 %", "11.b5", "11…♘a5found only 33 %"]);

  await user.click(screen.getByRole("button", { name: /^10\.Be3 O-O 11\.Nd5:/ }));
  expect(
    screen.getByRole("img", { name: "Position before 10.Be3 O-O 11.Nd5" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "The refutation" })).toHaveTextContent(
    "in 3 games of your reference database",
  );
});

test("a running search can be stopped, a finished one deleted", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateNovelty(aSearch({ status: "running", tries: [] }));
  renderApp("/novelty/7");
  const user = userEvent.setup();

  expect(await screen.findByText(/No tries yet/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Stop" }));
  await waitFor(() => {
    expect(received.cancelled).toBe(1);
  });

  simulateNovelty(aSearch());
  renderApp("/novelty/7");
  await user.click(await screen.findByRole("button", { name: "Delete" }));
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Delete" }));
  expect(await screen.findByRole("heading", { name: "Novelty searches" })).toBeVisible();
});

test("the searches are listed with their opponent and how far they got", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateNovelty(aSearch({ status: "running", own_moves: 2 }));
  renderApp("/novelty");

  const item = (await screen.findByRole("link", { name: "Smith-Morra, after 9.Rd1 e5" })).closest(
    "li",
  );

  expect(item).toHaveTextContent("For White · against FIDE 1800 (Maia 1962)");
  expect(item).toHaveTextContent("Searching: 2 of your moves deep so far.");
});
