import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";
import type { Game } from "../games/games";
import type { AnalysisRun, GameAnalysis, PositionEval } from "./analysis";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

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
    ply_count: 4,
    source: "pgn",
    imported_at: "2026-10-22T12:00:00Z",
    tags: [],
    pgn: '[White "Anna"]\n[Black "Ben"]\n[Result "*"]\n\n1. e4 e5 2. Qh5 Ke7 *\n',
    import_run_id: null,
    collections: [],
  };
}

function aRun(fields: Partial<AnalysisRun> = {}): AnalysisRun {
  return {
    id: 1,
    game_id: 7,
    status: "done",
    depth: 18,
    positions_total: 5,
    positions_done: 5,
    error: "",
    created_at: "2026-10-23T12:00:00Z",
    started_at: "2026-10-23T12:00:01Z",
    finished_at: "2026-10-23T12:00:09Z",
    ...fields,
  };
}

function position(ply: number, win: number, fields: Partial<PositionEval> = {}): PositionEval {
  return {
    ply,
    depth: 18,
    score_cp: 20,
    score_mate: null,
    win_percent: win,
    best_move_uci: "e2e4",
    pv: [],
    move_class: ply === 0 ? null : "good",
    ...fields,
  };
}

const NO_MISTAKES = { inaccuracies: 0, mistakes: 0, blunders: 0 };

function notAnalysed(run: AnalysisRun | null = null): GameAnalysis {
  return { run, summary: null, positions: [], white: NO_MISTAKES, black: NO_MISTAKES };
}

function analysed(): GameAnalysis {
  return {
    run: aRun(),
    summary: {
      accuracy_white: 81.2,
      accuracy_black: 44.5,
      depth: 18,
      engine: "Stockfish 19",
      analysed_at: "2026-10-23T12:00:09Z",
    },
    positions: [
      position(0, 51.8, { pv: ["e2e4", "e7e5", "g1f3"] }),
      position(1, 53.0, { score_cp: 35 }),
      position(2, 52.0),
      position(3, 40.0, { score_cp: -80, move_class: "inaccuracy" }),
      position(4, 80.0, { score_cp: null, score_mate: 3, move_class: "blunder" }),
    ],
    white: { inaccuracies: 1, mistakes: 0, blunders: 0 },
    black: { inaccuracies: 0, mistakes: 0, blunders: 1 },
  };
}

/** The viewer of game 7, with the analysis answers given one after another (the last stays). */
function openGame(...answers: GameAnalysis[]) {
  const requests: unknown[] = [];
  let call = 0;
  server.use(
    http.get("*/api/v1/games/:gameId", () => HttpResponse.json(aGame())),
    http.get("*/api/v1/tags", () => HttpResponse.json({ items: [], total: 0 })),
    http.get("*/api/v1/collections", () => HttpResponse.json({ items: [], total: 0 })),
    http.get("*/api/v1/analysis/games/:gameId", () => {
      const answer = answers[Math.min(call, answers.length - 1)];
      call += 1;
      return HttpResponse.json(answer);
    }),
    http.post("*/api/v1/analysis", async ({ request }) => {
      requests.push(await request.json());
      return HttpResponse.json([aRun({ status: "queued" })], { status: 202 });
    }),
  );
  simulateAuth(alice, { loggedIn: true });
  renderApp("/games/7");
  return requests;
}

test("a game without analysis can be analysed", async () => {
  const requests = openGame(notAnalysed(), notAnalysed(aRun({ status: "queued" })));
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "Analyse with Stockfish" }));

  expect(await screen.findByText("Waiting for the engine…")).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Progress of the analysis" })).toBeInTheDocument();
  expect(requests).toEqual([{ game_ids: [7], depth: null }]);
  expect(screen.queryByRole("meter")).not.toBeInTheDocument(); // no bar without results
});

test("follows a running analysis until it is done", async () => {
  openGame(notAnalysed(aRun({ status: "running", positions_done: 3 })), analysed());

  expect(await screen.findByText("Analysing… 3 of 5 positions")).toBeInTheDocument();
  expect(await screen.findByText("81 %", {}, { timeout: 4000 })).toBeInTheDocument();
});

test("shows each player's accuracy and weak moves", async () => {
  openGame(analysed());

  const table = await screen.findByRole("table");
  const rows = within(table).getAllByRole("row");
  expect(rows[1]).toHaveTextContent(/White\s*81 %\s*1\s*0\s*0/);
  expect(rows[2]).toHaveTextContent(/Black\s*45 %\s*0\s*0\s*1/);
  expect(screen.getByText("Stockfish 19, depth 18")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Qh5 (inaccuracy)" })).toHaveTextContent("♕h5?!");
  expect(screen.getByRole("button", { name: "Ke7 (blunder)" })).toHaveTextContent("♔e7??");
  expect(screen.getByRole("img", { name: /Evaluation over the game/ })).toBeInTheDocument();
});

test("the bar and the best line follow the shown position", async () => {
  openGame(analysed());
  const user = userEvent.setup();

  const bar = await screen.findByRole("meter", { name: "Evaluation" });
  expect(bar).toHaveAttribute("aria-valuetext", "+0.20 for White");
  expect(screen.getByText("1. e4 e5 2. ♘f3")).toBeInTheDocument(); // figurines, as the moves

  await user.click(screen.getByRole("button", { name: "Ke7 (blunder)" }));

  expect(bar).toHaveAttribute("aria-valuetext", "#3 for White");
  expect(bar).toHaveAttribute("aria-valuenow", "80");
});

test("an analysed game can be analysed deeper", async () => {
  const requests = openGame(analysed());
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "Analyse deeper (depth 22)" }));

  await waitFor(() => {
    expect(requests).toEqual([{ game_ids: [7], depth: 22 }]);
  });
});

test("a failed analysis says why and can be tried again", async () => {
  openGame(notAnalysed(aRun({ status: "failed", error: "Stockfish isn't installed" })));

  expect(
    await screen.findByText(/The last analysis stopped: Stockfish isn't installed/),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Analyse with Stockfish" })).toBeInTheDocument();
});

test("clicking the graph goes to that position", async () => {
  openGame(analysed());

  const graph = await screen.findByRole("img", { name: /Evaluation over the game/ });
  graph.getBoundingClientRect = () => ({ left: 0, width: 400 }) as DOMRect;
  fireEvent.click(graph, { clientX: 300 }); // three quarters of four moves: after 2. Qh5

  expect(screen.getByRole("img", { name: "Position after 2. Qh5" })).toBeInTheDocument();
});
