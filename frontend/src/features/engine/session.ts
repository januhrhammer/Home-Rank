/**
 * One Stockfish in a Web Worker, analysing whatever position it is given (ADR 0018).
 *
 * UCI has one trap: a search must be stopped before the next one starts, and the engine still
 * reports on the old position until it answers "bestmove". So a new position waits for that
 * answer, and reports in between are ignored. No React here: the session is tested with a
 * fake worker, and useEngine wraps it.
 */
import { type EngineLine, parseInfo } from "./uci";

/** How deep a search goes before it stops by itself, so an open page doesn't run forever. */
export const MAX_DEPTH = 30;

/** The part of a Worker the session uses. */
export interface EngineWorker {
  postMessage: (message: string) => void;
  terminate: () => void;
  onmessage: ((event: { data: unknown }) => void) | null;
}

export interface SessionOptions {
  threads: number;
  /** How many lines to show (UCI's MultiPV). */
  lines: number;
  /** Called with the lines so far, best first, whenever one changes. */
  onLines: (fen: string, lines: EngineLine[]) => void;
}

type State = "starting" | "idle" | "searching" | "stopping";

export class EngineSession {
  private state: State = "starting";
  /** The position wanted next; null: none, stop. */
  private wanted: string | null = null;
  /** The position being searched, or last searched. */
  private current: string | null = null;
  /** Whether the last search reached MAX_DEPTH: then its lines stand, nothing to redo. */
  private finished = false;
  private lines = new Map<number, EngineLine>();

  constructor(
    private readonly worker: EngineWorker,
    private readonly options: SessionOptions,
  ) {
    worker.onmessage = (event) => {
      this.receive(String(event.data));
    };
    worker.postMessage("uci");
  }

  /** Analyse `fen` from now on, or stop with null. */
  analyse(fen: string | null): void {
    this.wanted = fen;
    if (this.state === "idle" && !(this.finished && fen === this.current)) {
      this.startWanted();
    } else if (this.state === "searching" && fen !== this.current) {
      this.state = "stopping";
      this.worker.postMessage("stop");
    }
    // "starting" and "stopping" go on with `wanted` when the engine is ready.
  }

  dispose(): void {
    this.worker.onmessage = null;
    this.worker.terminate();
  }

  private receive(line: string): void {
    if (line === "uciok") {
      this.worker.postMessage(`setoption name Threads value ${String(this.options.threads)}`);
      this.worker.postMessage(`setoption name MultiPV value ${String(this.options.lines)}`);
      this.worker.postMessage("isready");
    } else if (line === "readyok" && this.state === "starting") {
      this.state = "idle";
      this.startWanted();
    } else if (line.startsWith("bestmove")) {
      // A search ended: stopped for another position, or done at MAX_DEPTH.
      const stopped = this.state === "stopping";
      this.finished = !stopped;
      this.state = "idle";
      if (stopped) {
        this.startWanted();
      }
    } else if (this.state === "searching" && this.current !== null) {
      const whiteToMove = this.current.split(" ")[1] !== "b";
      const parsed = parseInfo(line, whiteToMove);
      if (parsed !== null && parsed.rank <= this.options.lines) {
        this.lines.set(parsed.rank, parsed);
        const best = [...this.lines.values()].sort((a, b) => a.rank - b.rank);
        this.options.onLines(this.current, best);
      }
    }
  }

  private startWanted(): void {
    if (this.wanted === null) {
      return;
    }
    this.current = this.wanted;
    this.finished = false;
    this.lines = new Map();
    this.state = "searching";
    this.worker.postMessage(`position fen ${this.current}`);
    this.worker.postMessage(`go depth ${String(MAX_DEPTH)}`);
  }
}
