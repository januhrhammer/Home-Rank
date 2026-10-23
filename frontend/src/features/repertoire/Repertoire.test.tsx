import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Chess } from "chessops/chess";
import { makeFen, parseFen } from "chessops/fen";
import { makeSan } from "chessops/san";
import { parseUci } from "chessops/util";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import { answerUploads } from "../../test/uploads";
import type { User } from "../auth";
import type { Repertoire, RepertoireMove } from "./repertoire";
import { movesOf } from "./testMoves";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

const QUEENS_GAMBIT: Repertoire = {
  id: 4,
  name: "Queen's Gambit",
  color: "white",
  move_count: 0,
  due: 0,
};

/**
 * A simulated repertoire API around `moves`, which it changes like the server would (roughly:
 * removing a move removes only that one). The explorer suggests 1. e4 and 1. d4 everywhere.
 * Returns what it received.
 */
function simulateRepertoire(moves: RepertoireMove[], repertoire = QUEENS_GAMBIT) {
  const received: { added: unknown[]; comments: unknown[]; removed: number[]; seeds: unknown[] } = {
    added: [],
    comments: [],
    removed: [],
    seeds: [],
  };
  const counted = () => ({ ...repertoire, move_count: moves.length });
  server.use(
    http.get("*/api/v1/repertoires", () => HttpResponse.json([counted()])),
    http.post("*/api/v1/repertoires", async ({ request }) => {
      const body = (await request.json()) as { name: string; color: "white" | "black" };
      return HttpResponse.json({ ...repertoire, id: 8, ...body }, { status: 201 });
    }),
    http.get("*/api/v1/repertoires/:id", ({ params }) =>
      Number(params.id) === repertoire.id
        ? HttpResponse.json(counted())
        : HttpResponse.json({ detail: "Not found." }, { status: 404 }),
    ),
    http.get("*/api/v1/repertoires/:id/moves", () => HttpResponse.json(moves)),
    http.post("*/api/v1/repertoires/:id/moves", async ({ request }) => {
      const body = (await request.json()) as { fen: string; move_uci: string };
      received.added.push(body);
      const move = played(body.fen, body.move_uci, moves.length + 1);
      moves.push(move);
      return HttpResponse.json(move, { status: 201 });
    }),
    http.patch("*/api/v1/repertoires/:id/moves/:moveId", async ({ request, params }) => {
      const body = (await request.json()) as { comment: string };
      received.comments.push(body);
      const move = moves.find((m) => m.id === Number(params.moveId));
      if (move) {
        move.comment = body.comment;
      }
      return HttpResponse.json(move);
    }),
    http.delete("*/api/v1/repertoires/:id/moves/:moveId", ({ params }) => {
      received.removed.push(Number(params.moveId));
      moves.splice(
        moves.findIndex((m) => m.id === Number(params.moveId)),
        1,
      );
      return HttpResponse.json({ removed: 1 });
    }),
    http.post("*/api/v1/repertoires/:id/seed", async ({ request }) => {
      received.seeds.push(await request.json());
      return HttpResponse.json({ moves_added: 37 });
    }),
    http.get("*/api/v1/reference/databases", () => HttpResponse.json([])),
    http.get("*/api/v1/explorer/my", () =>
      HttpResponse.json({
        games: 3,
        filtered: true,
        moves: [
          { uci: "e2e4", san: "e4", games: 2, white: 1, draws: 1, black: 0 },
          { uci: "d2d4", san: "d4", games: 1, white: 1, draws: 0, black: 0 },
        ].map((m) => ({ ...m, average_rating: null, last_played: null })),
      }),
    ),
  );
  return received;
}

/** A move as the server would add it; positions are named by their FEN without counters. */
function played(fen: string, uci: string, id: number): RepertoireMove {
  const position = Chess.fromSetup(parseFen(fen).unwrap()).unwrap();
  const move = parseUci(uci);
  if (move === undefined) {
    throw new Error(uci);
  }
  const san = makeSan(position, move);
  const userToMove = position.turn === "white";
  position.play(move);
  const name = (f: string) => f.split(" ").slice(0, 4).join(" ");
  return {
    id,
    from_position: name(fen),
    from_fen: fen,
    move_uci: uci,
    move_san: san,
    to_position: name(makeFen(position.toSetup())),
    comment: "",
    card_id: userToMove ? 100 + id : null,
  };
}

function moveList() {
  return screen.getByRole("group", { name: "Moves" });
}

test("lists my repertoires and creates one", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateRepertoire(movesOf([["d4", "d5"]]));
  renderApp("/repertoires");
  const user = userEvent.setup();

  expect(await screen.findByRole("link", { name: "Queen's Gambit" })).toBeInTheDocument();
  expect(screen.getByText(/For White · 2 moves/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "New repertoire" }));
  const dialog = screen.getByRole("dialog");
  await user.type(within(dialog).getByLabelText("Name"), "Najdorf");
  await user.click(within(dialog).getByRole("radio", { name: "Black" }));
  await user.click(within(dialog).getByRole("button", { name: "Create" }));

  // The new repertoire opens: the simulated API answers for id 8 with "not found".
  expect(await screen.findByText("There is no such repertoire.")).toBeInTheDocument();
});

test("a name already taken is explained with the server's words", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateRepertoire([]);
  server.use(
    http.post("*/api/v1/repertoires", () =>
      HttpResponse.json(
        { detail: 'You already have one called "Queen\'s Gambit".' },
        { status: 409 },
      ),
    ),
  );
  renderApp("/repertoires");
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "New repertoire" }));
  await user.type(screen.getByLabelText("Name"), "Queen's Gambit");
  await user.click(screen.getByRole("button", { name: "Create" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    'You already have one called "Queen\'s Gambit".',
  );
});

test("the editor shows the tree, and a move's line and comment", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateRepertoire(
    movesOf(
      [
        ["d4", "d5", "c4", "e6"],
        ["d4", "d5", "c4", "c6"],
      ],
      { comments: { c4: "The gambit." } },
    ),
  );
  renderApp("/repertoires/4");
  const user = userEvent.setup();

  expect(await screen.findByRole("heading", { name: "Queen's Gambit" })).toBeInTheDocument();
  expect(moveList()).toHaveTextContent("1.d4d52.c4The gambit.2…e6(2…c6)");

  await user.click(within(moveList()).getByRole("button", { name: "c4" }));
  expect(screen.getByRole("heading", { name: "1. d4 d5 2. c4" })).toBeInTheDocument();
  expect(screen.getByText(/Your move/)).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Position after 1. d4 d5 2. c4" })).toBeInTheDocument();

  const comment = screen.getByLabelText("Comment");
  expect(comment).toHaveValue("The gambit.");
  await user.clear(comment);
  await user.type(comment, "Main line.");
  await user.click(screen.getByRole("button", { name: "Save comment" }));

  expect(await screen.findByText("Comment saved.")).toBeInTheDocument();
  expect(received.comments).toEqual([{ comment: "Main line." }]);
});

test("a move chosen in the explorer is added and shown", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateRepertoire([]);
  renderApp("/repertoires/4");
  const user = userEvent.setup();

  expect(await screen.findByText(/No moves yet/)).toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: "d4" }));

  expect(await screen.findByRole("heading", { name: "1. d4" })).toBeInTheDocument();
  expect(received.added).toEqual([
    { fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", move_uci: "d2d4" },
  ]);
  expect(within(moveList()).getByRole("button", { name: "d4" })).toHaveAttribute(
    "aria-current",
    "step",
  );
});

test("a move typed in is added, for keyboards and screen readers", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateRepertoire([]);
  renderApp("/repertoires/4");
  const user = userEvent.setup();

  const field = await screen.findByRole("textbox", { name: "Play a move" });
  await user.type(field, "Nf6");
  await user.click(screen.getByRole("button", { name: "Play" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("That move isn't possible here.");

  await user.clear(field);
  await user.type(field, "Nf3{Enter}");

  expect(await screen.findByRole("heading", { name: "1. Nf3" })).toBeInTheDocument();
  expect(received.added).toEqual([
    { fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", move_uci: "g1f3" },
  ]);
  expect(field).toHaveValue("");
});

test("a move already in the repertoire is followed, not added again", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateRepertoire(movesOf([["d4", "d5"]]));
  renderApp("/repertoires/4");
  const user = userEvent.setup();

  await screen.findByRole("group", { name: "Moves" });
  const explorer = await screen.findByRole("table");
  await user.click(within(explorer).getByRole("button", { name: "d4" }));

  expect(await screen.findByRole("heading", { name: "1. d4" })).toBeInTheDocument();
  expect(received.added).toEqual([]);
});

test("a refused move is explained with the server's words", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateRepertoire([]);
  server.use(
    http.post("*/api/v1/repertoires/:id/moves", () =>
      HttpResponse.json({ detail: "A repertoire can have at most 20,000 moves." }, { status: 409 }),
    ),
  );
  renderApp("/repertoires/4");
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "e4" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "A repertoire can have at most 20,000 moves.",
  );
});

test("a transposition leads to where its moves are shown", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateRepertoire(
    movesOf([
      ["e4", "e5", "Nf3"],
      ["e3", "e6", "e4", "e5"],
    ]),
  );
  renderApp("/repertoires/4");
  const user = userEvent.setup();

  await screen.findByRole("group", { name: "Moves" });
  expect(moveList()).toHaveTextContent("Same position as after 1. e4 e5.");
  // The other way is printed as a variation after 1. e4, so its 2… e5 comes first.
  const [transposed] = within(moveList()).getAllByRole("button", { name: "e5" });
  await user.click(transposed as HTMLElement);
  expect(screen.getByRole("heading", { name: "1. e3 e6 2. e4 e5" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Its moves are shown after 1\. e4 e5/ }));

  expect(screen.getByRole("heading", { name: "1. e4 e5" })).toBeInTheDocument();
  await user.keyboard("{ArrowRight}");
  expect(screen.getByRole("heading", { name: "1. e4 e5 2. Nf3" })).toBeInTheDocument();
});

test("removing a move asks first, then shows the move before it", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateRepertoire(movesOf([["d4", "d5", "c4"]]));
  renderApp("/repertoires/4");
  const user = userEvent.setup();

  await user.click(
    await within(await screen.findByRole("group", { name: "Moves" })).findByRole("button", {
      name: "c4",
    }),
  );
  await user.click(screen.getByRole("button", { name: "Remove move" }));
  const dialog = screen.getByRole("alertdialog");
  expect(dialog).toHaveTextContent("Remove 1. d4 d5 2. c4?");
  await user.click(within(dialog).getByRole("button", { name: "Remove" }));

  expect(await screen.findByRole("heading", { name: "1. d4 d5" })).toBeInTheDocument();
  expect(received.removed).toEqual([3]);
  expect(within(moveList()).queryByRole("button", { name: "c4" })).not.toBeInTheDocument();
});

test("seeding from my games sends the depth and minimum, and says what was added", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateRepertoire([]);
  renderApp("/repertoires/4");
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "From my games" }));
  const dialog = screen.getByRole("dialog");
  const depth = within(dialog).getByLabelText("Half-moves from the start");
  await user.clear(depth);
  await user.type(depth, "8");
  await user.click(within(dialog).getByRole("button", { name: "Add moves" }));

  expect(await within(dialog).findByText("Added 37 moves.")).toBeInTheDocument();
  expect(received.seeds).toEqual([{ depth: 8, min_games: 2 }]);
});

test("importing sends the chosen file and says what was added", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateRepertoire([]);
  const sent = answerUploads(() =>
    HttpResponse.json({ moves_added: 120, games_read: 14, games_skipped: 2 }),
  );
  renderApp("/repertoires/4");
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "Import PGN" }));
  const dialog = screen.getByRole("dialog");
  const input = dialog.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) {
    throw new Error("no file input");
  }
  await user.upload(
    input,
    new File(["1. d4 *"], "course.pgn", { type: "application/x-chess-pgn" }),
  );
  await user.click(within(dialog).getByRole("button", { name: "Import" }));

  expect(await within(dialog).findByRole("status")).toHaveTextContent(
    "Added 120 moves from 14 games. 2 games were skipped",
  );
  expect(sent).toEqual([{ url: "/api/v1/repertoires/4/import", fields: ["file"] }]);
});

test("someone else's repertoire isn't found", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateRepertoire([]);
  server.use(
    http.get("*/api/v1/repertoires/:id/moves", () =>
      HttpResponse.json({ detail: "Not found." }, { status: 404 }),
    ),
  );
  renderApp("/repertoires/99");

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent("There is no such repertoire.");
  });
});
