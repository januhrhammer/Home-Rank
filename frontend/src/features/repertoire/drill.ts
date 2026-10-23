import { queryOptions, useMutation } from "@tanstack/react-query";
import { Chess } from "chessops/chess";
import { makeFen, parseFen } from "chessops/fen";
import { parseUci } from "chessops/util";

import { api } from "../../api/client";
import { ApiError, problemDetail } from "../../api/errors";
import type { components } from "../../api/schema";
import { REPERTOIRE_KEY } from "./repertoire";

export type DrillStep = components["schemas"]["DrillStepOut"];
export type DueDrill = components["schemas"]["DueDrillOut"];
export type Gap = components["schemas"]["GapOut"];

function unwrap<T>({
  data,
  error,
  response,
}: {
  data?: T;
  error?: unknown;
  response: Response;
}): T {
  if (data === undefined) {
    throw new ApiError(response.status, problemDetail(error));
  }
  return data;
}

// Under the repertoire queries' key, so that a change to the repertoire refreshes them too.
// The drill's own queries are fetched again only when the user goes on (they are never
// "stale"), not when the window gets the focus back: that would swap the card, or restart the
// line, in the middle of an answer.

export function nextDueQuery(repertoireId: number) {
  return queryOptions({
    queryKey: [...REPERTOIRE_KEY, repertoireId, "drill", "next"],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/repertoires/{repertoire_id}/drill/next", {
          params: { path: { repertoire_id: repertoireId } },
        }),
      ),
    staleTime: Infinity,
  });
}

export function lineQuery(repertoireId: number, through: number | null) {
  return queryOptions({
    queryKey: [...REPERTOIRE_KEY, repertoireId, "drill", "line", through],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/repertoires/{repertoire_id}/drill/line", {
          params: { path: { repertoire_id: repertoireId }, query: { through } },
        }),
      ),
    staleTime: Infinity,
  });
}

export function gapsQuery(repertoireId: number) {
  return queryOptions({
    queryKey: [...REPERTOIRE_KEY, repertoireId, "gaps"],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/repertoires/{repertoire_id}/gaps", {
          params: { path: { repertoire_id: repertoireId } },
        }),
      ),
  });
}

/**
 * Records an answer to a card: right on the first try is rated Good, otherwise Again (ADR
 * 0016). Nothing is refreshed, so the card stays on screen until the user goes on.
 */
export function useDrillReview() {
  return useMutation({
    mutationFn: async (answer: { cardId: number; correct: boolean; elapsedMs: number }) =>
      unwrap(
        await api.POST("/api/v1/training/reviews", {
          body: {
            card_id: answer.cardId,
            correct: answer.correct,
            elapsed_ms: answer.elapsedMs,
          },
        }),
      ),
  });
}

/**
 * What a move played in a drill means: the move asked for, another of the repertoire's own
 * moves in this position (not wrong, but not this card's), or a wrong one.
 */
export type Answer = "right" | "other" | "wrong";

export function judge(step: DrillStep, uci: string): Answer {
  if (uci === step.move_uci) {
    return "right";
  }
  return step.other_moves.includes(uci) ? "other" : "wrong";
}

/** The position after a legal move in UCI. */
export function fenAfter(fen: string, uci: string): string {
  const position = Chess.fromSetup(parseFen(fen).unwrap()).unwrap();
  const move = parseUci(uci);
  if (move === undefined || !position.isLegal(move)) {
    throw new Error(`illegal move ${uci} in ${fen}`);
  }
  position.play(move);
  return makeFen(position.toSetup());
}
