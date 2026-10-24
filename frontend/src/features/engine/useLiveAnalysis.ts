import { useEffect, useRef, useState } from "react";

import { EngineSession, type EngineWorker } from "./session";
import type { EngineLine } from "./uci";

/** Lines shown: the best three, as on Lichess. */
const LINES = 3;
/** The page shows new lines at most this often (ms): the engine reports far more often. */
const SHOW_EVERY = 150;
const STORAGE_KEY = "home-rank.live-analysis";

export interface LiveAnalysis {
  enabled: boolean;
  setEnabled: (enabled: boolean) => void;
  /** The engine's lines for the position asked about, best first; empty until the first. */
  lines: EngineLine[];
}

/**
 * Stockfish in the browser, analysing `fen` while live analysis is on (ADR 0018); null is a
 * position not to analyse, e.g. an illegal one being set up. The engine
 * starts the first time it is switched on, and stops when the page goes. Whether it is on is
 * kept in the browser, like the notation.
 */
export function useLiveAnalysis(fen: string | null): LiveAnalysis {
  const [enabled, setEnabled] = useState(storedEnabled);
  const [shown, setShown] = useState<{ fen: string; lines: EngineLine[] } | null>(null);
  const sessionRef = useRef<EngineSession | null>(null);
  const latestRef = useRef<{ fen: string; lines: EngineLine[] } | null>(null);
  const timerRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (enabled && sessionRef.current === null) {
      sessionRef.current = new EngineSession(createEngineWorker(), {
        threads: engineThreads(),
        lines: LINES,
        onLines: (linesFen, lines) => {
          latestRef.current = { fen: linesFen, lines };
          timerRef.current ??= window.setTimeout(() => {
            timerRef.current = undefined;
            setShown(latestRef.current);
          }, SHOW_EVERY);
        },
      });
    }
    sessionRef.current?.analyse(enabled ? fen : null);
  }, [fen, enabled]);

  useEffect(
    () => () => {
      window.clearTimeout(timerRef.current);
      sessionRef.current?.dispose();
      sessionRef.current = null;
    },
    [],
  );

  const changeEnabled = (next: boolean) => {
    setEnabled(next);
    try {
      localStorage.setItem(STORAGE_KEY, next ? "on" : "off");
    } catch {
      // Storage can be blocked: then the choice lasts this visit.
    }
  };

  return {
    enabled,
    setEnabled: changeEnabled,
    lines: enabled && shown?.fen === fen ? shown.lines : [],
  };
}

function storedEnabled(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "on";
  } catch {
    return false;
  }
}

/**
 * The engine's worker: multi-threaded where the page may share memory between threads
 * (cross-origin isolated, see backend/homerank/core/isolation.py), single-threaded otherwise.
 * The files come from the stockfish package (vite.config.ts serves them at /engine/).
 */
export function createEngineWorker(): EngineWorker {
  const file = crossOriginIsolated ? "stockfish-19-lite.js" : "stockfish-19-lite-single.js";
  const worker = new Worker(`/engine/${file}`);
  const engine: EngineWorker = {
    postMessage: (message) => {
      worker.postMessage(message);
    },
    terminate: () => {
      worker.terminate();
    },
    onmessage: null,
  };
  worker.onmessage = (event) => engine.onmessage?.({ data: event.data });
  return engine;
}

/** All cores but one, at most 4: the page and the rest of the computer stay responsive. */
function engineThreads(): number {
  return crossOriginIsolated ? Math.max(1, Math.min(4, navigator.hardwareConcurrency - 1)) : 1;
}
