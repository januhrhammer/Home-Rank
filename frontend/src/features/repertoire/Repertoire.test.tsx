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
import type { Conflict, Repertoire, RepertoireLine, RepertoireMove } from "./repertoire";
import { movesOf } from "./testMoves";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

const QUEENS_GAMBIT: Repertoire = {
  id: 4,
  name: "Queen's Gambit",
  color: "white",
  line_count: 1,
  move_count: 0,
  due: 0,
};

/**
 * A simulated repertoire API around `moves`, which it changes like the server would (roughly:
 * removing a move removes only that one, from the line named). It starts with one line, "Main
 * line" (id 1), holding all the moves. The explorer suggests 1. e4 and 1. d4 everywhere.
 * Returns what it received.
 */
function simulateRepertoire(
  moves: RepertoireMove[],
  repertoire = QUEENS_GAMBIT,
  conflicts: Conflict[] = [],
) {
  const received: {
    added: unknown[];
    comments: unknown[];
    removed: string[];
    seeds: unknown[];
    orders: unknown[];
  } = {
    added: [],
    comments: [],
    removed: [],
    seeds: [],
    orders: [],
  };
  const lines: RepertoireLine[] = [{ id: 1, name: "Main line", position: 0, move_count: 0 }];
  const counted = () => ({ ...repertoire, move_count: moves.length, line_count: lines.length });
  const listed = () =>
    lines.map((line) => ({
      ...line,
      move_count: moves.filter((m) => m.line_ids.includes(line.id)).length,
    }));
  server.use(
    http.get("*/api/v1/repertoires/:id/conflicts", () => HttpResponse.json(conflicts)),
    http.get("*/api/v1/repertoires/:id/lines", () => HttpResponse.json(listed())),
    http.post("*/api/v1/repertoires/:id/lines", async ({ request }) => {
      const { name } = (await request.json()) as { name: string };
      const line = { id: lines.length + 1, name, position: lines.length, move_count: 0 };
      lines.push(line);
      return HttpResponse.json(line, { status: 201 });
    }),
    http.put("*/api/v1/repertoires/:id/lines/order", async ({ request }) => {
      const { line_ids } = (await request.json()) as { line_ids: number[] };
      received.orders.push(line_ids);
      lines.sort((a, b) => line_ids.indexOf(a.id) - line_ids.indexOf(b.id));
      return HttpResponse.json(listed());
    }),
    http.patch("*/api/v1/repertoires/:id/lines/:lineId", async ({ request, params }) => {
      const { name } = (await request.json()) as { name: string };
      const line = lines.find((l) => l.id === Number(params.lineId));
      if (line) {
        line.name = name;
      }
      return HttpResponse.json(line);
    }),
    http.delete("*/api/v1/repertoires/:id/lines/:lineId", ({ params }) => {
      lines.splice(
        lines.findIndex((l) => l.id === Number(params.lineId)),
        1,
      );
      return HttpResponse.json({ removed: 0 });
    }),
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
      const body = (await request.json()) as { fen: string; move_uci: string; line_id?: number };
      received.added.push(body);
      const known = moves.find((m) => m.from_fen === body.fen && m.move_uci === body.move_uci);
      if (known) {
        known.line_ids = [...known.line_ids, body.line_id ?? 1];
        return HttpResponse.json(known, { status: 201 });
      }
      const move = { ...played(body.fen, body.move_uci, moves.length + 1) };
      move.line_ids = [body.line_id ?? 1];
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
    http.delete("*/api/v1/repertoires/:id/moves/:moveId", ({ params, request }) => {
      const lineId = new URL(request.url).searchParams.get("line_id");
      received.removed.push(`${String(params.moveId)} from ${String(lineId)}`);
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
    line_ids: [1],
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

  expect(await screen.findByText(/No moves in this line yet/)).toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: "d4" }));

  expect(await screen.findByRole("heading", { name: "1. d4" })).toBeInTheDocument();
  expect(received.added).toEqual([
    {
      fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      move_uci: "d2d4",
      line_id: 1,
    },
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
    {
      fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      move_uci: "g1f3",
      line_id: 1,
    },
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
  await user.click(screen.getByRole("button", { name: "Remove from this line" }));
  const dialog = screen.getByRole("alertdialog");
  expect(dialog).toHaveTextContent("Remove 1. d4 d5 2. c4 from Main line?");
  await user.click(within(dialog).getByRole("button", { name: "Remove" }));

  expect(await screen.findByRole("heading", { name: "1. d4 d5" })).toBeInTheDocument();
  expect(received.removed).toEqual(["3 from 1"]);
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
  expect(within(dialog).getByText("The moves go into the line Main line.")).toBeInTheDocument();
  expect(received.seeds).toEqual([{ depth: 8, min_games: 2, line_id: 1 }]);
});

test("importing sends the chosen file and says what was added", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateRepertoire([]);
  const sent = answerUploads(() =>
    HttpResponse.json({ moves_added: 120, games_read: 14, games_skipped: 2, lines_created: 0 }),
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
  expect(sent).toEqual([{ url: "/api/v1/repertoires/4/import?line_id=1", fields: ["file"] }]);
});

test("a course imports as one new line per chapter", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateRepertoire([]);
  const sent = answerUploads(() =>
    HttpResponse.json({ moves_added: 300, games_read: 12, games_skipped: 0, lines_created: 12 }),
  );
  renderApp("/repertoires/4");
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "Import PGN" }));
  const dialog = screen.getByRole("dialog");
  const input = dialog.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) {
    throw new Error("no file input");
  }
  await user.upload(input, new File(["1. d4 *"], "course.pgn"));
  await user.click(within(dialog).getByText(/as one new line per game/));
  await user.click(within(dialog).getByRole("button", { name: "Import" }));

  expect(await within(dialog).findByRole("status")).toHaveTextContent(
    "Added 12 new lines, one per game, with 300 moves new to the repertoire.",
  );
  expect(sent).toEqual([{ url: "/api/v1/repertoires/4/import?chapters=true", fields: ["file"] }]);
});

test("a new line starts empty, and moves of other lines can join it", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateRepertoire(movesOf([["d4", "d5", "c4"]]));
  renderApp("/repertoires/4");
  const user = userEvent.setup();
  const lines = await screen.findByRole("region", { name: "Lines" });

  await user.click(within(lines).getByRole("button", { name: "New line" }));
  await user.type(screen.getByLabelText("Name"), "Slav");
  await user.click(screen.getByRole("button", { name: "Create" }));

  expect(await within(lines).findByRole("link", { name: "Slav 0", current: "page" })).toBeVisible();
  expect(await screen.findByText(/No moves in this line yet/)).toBeInTheDocument();
  const elsewhere = screen.getByRole("region", { name: "Here in other lines" });
  await user.click(within(elsewhere).getByRole("button", { name: "d4 (Main line)" }));

  await waitFor(() => {
    expect(received.added).toEqual([
      {
        fen: expect.stringContaining("rnbqkbnr/pppppppp") as unknown,
        move_uci: "d2d4",
        line_id: 2,
      },
    ]);
  });
  expect(await within(moveList()).findByRole("button", { name: "d4" })).toBeInTheDocument();
  // Main line's 1…d5 is offered here next.
  expect(
    within(screen.getByRole("region", { name: "Here in other lines" })).getByRole("button", {
      name: "d5 (Main line)",
    }),
  ).toBeInTheDocument();
});

test("lines are reordered, renamed and deleted, saying how many moves go", async () => {
  simulateAuth(alice, { loggedIn: true });
  const received = simulateRepertoire(movesOf([["d4", "d5", "c4"]]));
  renderApp("/repertoires/4");
  const user = userEvent.setup();
  const lines = await screen.findByRole("region", { name: "Lines" });
  await user.click(within(lines).getByRole("button", { name: "New line" }));
  await user.type(screen.getByLabelText("Name"), "Slav");
  await user.click(screen.getByRole("button", { name: "Create" }));
  await within(lines).findByRole("link", { name: "Slav 0", current: "page" });

  await user.click(within(lines).getByRole("button", { name: "Move line up" }));
  await waitFor(() => {
    expect(received.orders).toEqual([[2, 1]]);
  });
  await user.click(within(lines).getByRole("button", { name: "Rename line" }));
  const name = screen.getByLabelText("Name");
  await user.clear(name);
  await user.type(name, "Semi-Slav");
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(await within(lines).findByRole("link", { name: "Semi-Slav 0" })).toBeInTheDocument();

  await user.click(within(lines).getByRole("link", { name: "Main line 3" }));
  await user.click(within(lines).getByRole("button", { name: "Delete line" }));
  const dialog = screen.getByRole("alertdialog");
  expect(dialog).toHaveTextContent("Delete the line Main line?");
  expect(dialog).toHaveTextContent("3 of its moves are in no other line");
  await user.click(within(dialog).getByRole("button", { name: "Delete" }));

  await waitFor(() => {
    expect(
      within(within(lines).getByRole("list"))
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Semi-Slav 0"]);
  });
  expect(within(lines).queryByRole("button", { name: "Delete line" })).not.toBeInTheDocument();
});

test("a line is drilled alone, or several chosen lines together", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateRepertoire(movesOf([["d4", "d5", "c4"]]));
  renderApp("/repertoires/4");
  const user = userEvent.setup();
  const lines = await screen.findByRole("region", { name: "Lines" });
  expect(within(lines).getByRole("link", { name: "Drill this line" })).toHaveAttribute(
    "href",
    "/repertoires/4/drill?line=1",
  );
  expect(within(lines).queryByRole("button", { name: "Drill several lines…" })).toBeNull();

  await user.click(within(lines).getByRole("button", { name: "New line" }));
  await user.type(screen.getByLabelText("Name"), "Slav");
  await user.click(screen.getByRole("button", { name: "Create" }));
  await user.click(await within(lines).findByRole("button", { name: "Drill several lines…" }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByRole("button", { name: "Drill 0 lines" })).toBeDisabled();
  await user.click(within(dialog).getByText("Main line"));
  await user.click(within(dialog).getByText("Slav"));
  await user.click(within(dialog).getByRole("button", { name: "Drill 2 lines" }));

  expect(await screen.findByRole("heading", { name: "Drill: Queen's Gambit" })).toBeVisible();
  expect(await screen.findByText(/Only the lines Main line, Slav/)).toBeInTheDocument();
});

test("positions where lines disagree are listed, with links to the lines", async () => {
  simulateAuth(alice, { loggedIn: true });
  simulateRepertoire(movesOf([["d4", "d5", "c4"]]), QUEENS_GAMBIT, [
    {
      fen: "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2",
      choices: [
        { move_uci: "c2c4", move_san: "c4", lines: ["Main line"] },
        { move_uci: "c1f4", move_san: "Bf4", lines: ["London"] },
      ],
    },
  ]);
  renderApp("/repertoires/4");

  const conflicts = await screen.findByRole("region", { name: "Where your lines disagree" });

  expect(within(conflicts).getByRole("listitem")).toHaveTextContent(
    // The figurine is shown, and Bf4 written out for screen readers.
    "2.c4 Main line · 2.♗f4Bf4 London",
  );
  expect(within(conflicts).getByRole("link", { name: "Main line" })).toHaveAttribute(
    "href",
    "/repertoires/4?line=1",
  );
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
