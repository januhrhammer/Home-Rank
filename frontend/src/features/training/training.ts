import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components, operations } from "../../api/schema";

export type Puzzle = components["schemas"]["PuzzleOut"];
export type Review = components["schemas"]["ReviewOut"];
export type Rating = Review["rating"];
export type TrainingStats = components["schemas"]["TrainingStatsOut"];
export type PuzzleFilters = NonNullable<
  operations["homerank_training_api_next_puzzle"]["parameters"]["query"]
>;

/** The start of every training query's key, to refresh them all after a review. */
const TRAINING_KEY = ["training"] as const;

export function nextPuzzleQuery(filters: PuzzleFilters) {
  return queryOptions({
    queryKey: [...TRAINING_KEY, "next", filters],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/v1/training/next", {
        params: { query: filters },
      });
      if (data === undefined) {
        throw new ApiError(response.status);
      }
      return data;
    },
    // A puzzle stays on screen while it is solved, even if the window regains focus.
    refetchOnWindowFocus: false,
  });
}

export const statsQuery = queryOptions({
  queryKey: [...TRAINING_KEY, "stats"],
  queryFn: async (): Promise<TrainingStats> => {
    const { data, response } = await api.GET("/api/v1/training/stats");
    if (data === undefined) {
      throw new ApiError(response.status);
    }
    return data;
  },
});

export function useStats() {
  return useQuery(statsQuery);
}

/** Records a solve; the server rates it and schedules the puzzle again. */
export function useReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (solve: { cardId: number; correct: boolean; elapsedMs: number }) => {
      const { data, response } = await api.POST("/api/v1/training/reviews", {
        body: { card_id: solve.cardId, correct: solve.correct, elapsed_ms: solve.elapsedMs },
      });
      if (data === undefined) {
        throw new ApiError(response.status);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: statsQuery.queryKey }),
  });
}

/** Changes the rating of the latest review. */
export function useChangeRating() {
  return useMutation({
    mutationFn: async ({ reviewId, rating }: { reviewId: number; rating: Rating }) => {
      const { data, response } = await api.PATCH("/api/v1/training/reviews/{review_id}", {
        params: { path: { review_id: reviewId } },
        body: { rating },
      });
      if (data === undefined) {
        throw new ApiError(response.status);
      }
      return data;
    },
  });
}

/** Refreshes the next puzzle and the statistics, to go on after a puzzle. */
export function useNextPuzzle() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: TRAINING_KEY });
}
