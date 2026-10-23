import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components } from "../../api/schema";

export type GameAnalysis = components["schemas"]["GameAnalysisOut"];
export type PositionEval = components["schemas"]["PositionEvalOut"];
export type AnalysisRun = components["schemas"]["AnalysisRunOut"];
export type MoveClass = NonNullable<PositionEval["move_class"]>;
export type AnalysisSettings = components["schemas"]["AnalysisSettingsOut"];
export type AnalysisSettingsChanges = components["schemas"]["AnalysisSettingsPatch"];

/** How often a game's analysis refreshes while it is waiting or running, in milliseconds. */
export const POLL_INTERVAL = 1500;

export function isActive(run: AnalysisRun | null): boolean {
  return run?.status === "queued" || run?.status === "running";
}

export async function fetchGameAnalysis(gameId: number): Promise<GameAnalysis> {
  const { data, response } = await api.GET("/api/v1/analysis/games/{game_id}", {
    params: { path: { game_id: gameId } },
  });
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data;
}

/** The start of every game analysis's query key, to refresh them all at once. */
const ANALYSIS_KEY = ["analysis"] as const;

export function gameAnalysisQuery(gameId: number) {
  return queryOptions({
    queryKey: [...ANALYSIS_KEY, gameId],
    queryFn: () => fetchGameAnalysis(gameId),
  });
}

export function useGameAnalysis(gameId: number) {
  return useQuery({
    ...gameAnalysisQuery(gameId),
    // Refresh to show the progress while the analysis waits or runs, and stop afterwards.
    refetchInterval: (query) => (isActive(query.state.data?.run ?? null) ? POLL_INTERVAL : false),
  });
}

/** Queues an analysis of the game, then refreshes it, which starts showing the progress. */
export function useAnalyse(gameId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (depth?: number) => {
      const { data, response } = await api.POST("/api/v1/analysis", {
        body: { game_ids: [gameId], depth: depth ?? null },
      });
      if (data === undefined) {
        throw new ApiError(response.status);
      }
      return data;
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: gameAnalysisQuery(gameId).queryKey }),
  });
}

export const analysisSettingsQuery = queryOptions({
  queryKey: ["analysis-settings"],
  queryFn: async (): Promise<AnalysisSettings> => {
    const { data, response } = await api.GET("/api/v1/analysis/settings");
    if (data === undefined) {
      throw new ApiError(response.status);
    }
    return data;
  },
});

/** Saves changes, keeps the server's answer, and reclassifies the moves of loaded games. */
export function useSaveAnalysisSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (changes: AnalysisSettingsChanges): Promise<AnalysisSettings> => {
      const { data, response } = await api.PATCH("/api/v1/analysis/settings", { body: changes });
      if (data === undefined) {
        throw new ApiError(response.status);
      }
      return data;
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(analysisSettingsQuery.queryKey, saved);
      void queryClient.invalidateQueries({ queryKey: ANALYSIS_KEY });
    },
  });
}

/** A score as players read it, from White's side: "+0.42", "−1.30", "#3", "#−2". */
export function formatScore(position: PositionEval): string {
  if (position.score_mate !== null) {
    if (position.score_mate === 0) {
      return "#";
    }
    return position.score_mate > 0
      ? `#${String(position.score_mate)}`
      : `#−${String(-position.score_mate)}`;
  }
  const pawns = (position.score_cp ?? 0) / 100;
  const sign = pawns > 0 ? "+" : pawns < 0 ? "−" : "";
  return `${sign}${Math.abs(pawns).toFixed(2)}`;
}
