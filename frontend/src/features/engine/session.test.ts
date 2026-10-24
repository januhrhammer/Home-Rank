import { expect, test } from "vitest";

import { EngineSession, type EngineWorker, MAX_DEPTH } from "./session";
import type { EngineLine } from "./uci";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";

/** A worker that records what it is told, and says what the test makes it say. */
function fakeWorker() {
  const sent: string[] = [];
  const worker: EngineWorker & { say: (line: string) => void; terminated: boolean } = {
    postMessage: (message) => sent.push(message),
    terminate: () => {
      worker.terminated = true;
    },
    onmessage: null,
    say: (line) => worker.onmessage?.({ data: line }),
    terminated: false,
  };
  return { worker, sent };
}

function start() {
  const { worker, sent } = fakeWorker();
  const reports: [string, EngineLine[]][] = [];
  const session = new EngineSession(worker, {
    threads: 3,
    lines: 2,
    onLines: (fen, lines) => reports.push([fen, lines]),
  });
  worker.say("uciok");
  return { worker, sent, reports, session };
}

test("the engine is set up, then searches the position wanted", () => {
  const { worker, sent, session } = start();
  session.analyse(START);
  expect(sent.at(-1)).toBe("isready"); // not ready yet: the position waits

  worker.say("readyok");

  expect(sent).toEqual([
    "uci",
    "setoption name Threads value 3",
    "setoption name MultiPV value 2",
    "isready",
    `position fen ${START}`,
    `go depth ${String(MAX_DEPTH)}`,
  ]);
});

test("its lines are reported best first, scored from White's side", () => {
  const { worker, reports, session } = start();
  worker.say("readyok");
  session.analyse(AFTER_E4);

  worker.say("info depth 10 multipv 2 score cp 10 pv e7e5");
  worker.say("info depth 10 multipv 1 score cp -20 pv c7c5");
  worker.say("info depth 10 multipv 3 score cp 0 pv e7e6"); // more than asked for

  const [fen, lines] = reports.at(-1) ?? ["", []];
  expect(fen).toBe(AFTER_E4);
  expect(lines.map((line) => [line.rank, line.score, line.moves[0]])).toEqual([
    [1, { cp: 20 }, "c7c5"],
    [2, { cp: -10 }, "e7e5"],
  ]);
});

test("a new position waits until the old search has stopped, and old reports are ignored", () => {
  const { worker, sent, reports, session } = start();
  worker.say("readyok");
  session.analyse(START);

  session.analyse(AFTER_E4);
  expect(sent.at(-1)).toBe("stop");
  worker.say("info depth 15 multipv 1 score cp 30 pv e2e4"); // still about START
  expect(reports).toEqual([]);

  worker.say("bestmove e2e4");
  expect(sent.slice(-2)).toEqual([`position fen ${AFTER_E4}`, `go depth ${String(MAX_DEPTH)}`]);
});

test("stopping stops, and a search done by itself doesn't start again", () => {
  const { worker, sent, session } = start();
  worker.say("readyok");
  session.analyse(START);
  worker.say("bestmove e2e4"); // reached MAX_DEPTH
  const count = sent.length;

  session.analyse(START);
  session.analyse(null);
  expect(sent.length).toBe(count);

  session.analyse(AFTER_E4);
  session.analyse(null);
  expect(sent.at(-1)).toBe("stop");
  worker.say("bestmove c7c5");
  expect(sent.at(-1)).toBe("stop"); // nothing new started
});

test("a position stopped half-way is searched again when wanted again", () => {
  const { worker, sent, session } = start();
  worker.say("readyok");
  session.analyse(START);
  session.analyse(null); // e.g. the user turned analysis off
  worker.say("bestmove e2e4");

  session.analyse(START);

  expect(sent.slice(-2)).toEqual([`position fen ${START}`, `go depth ${String(MAX_DEPTH)}`]);
});

test("disposing ends the worker", () => {
  const { worker, session } = start();

  session.dispose();

  expect(worker.terminated).toBe(true);
});
