import { keepPreviousData, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError, problemDetail } from "../../api/errors";
import type { components } from "../../api/schema";

export type Search = components["schemas"]["SearchOut"];
export type SearchDetail = components["schemas"]["SearchDetailOut"];
export type NoveltyTry = components["schemas"]["TryOut"];
export type NewSearch = components["schemas"]["SearchIn"];
export type RatingKind = components["schemas"]["RatingKind"];

/** The start of every novelty query's key, to refresh them all after a change. */
export const NOVELTY_KEY = ["novelty"] as const;

/** How often a waiting or running search is fetched again, in milliseconds. */
const WATCH_MS = 15_000;

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

/** Whether a search may still change: it waits or runs. */
export function isActive(search: Search): boolean {
  return search.status === "queued" || search.status === "running";
}

export const searchesQuery = queryOptions({
  queryKey: [...NOVELTY_KEY, "list"],
  queryFn: async () =>
    unwrap(await api.GET("/api/v1/novelty/searches", { params: { query: { limit: 100 } } })),
  // Fetched again while one of them is still searching.
  refetchInterval: (query) => (query.state.data?.items.some(isActive) === true ? WATCH_MS : false),
});

export function searchQuery(searchId: number) {
  return queryOptions({
    queryKey: [...NOVELTY_KEY, searchId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/novelty/searches/{search_id}", {
          params: { path: { search_id: searchId } },
        }),
      ),
    refetchInterval: (query) =>
      query.state.data !== undefined && isActive(query.state.data) ? WATCH_MS : false,
  });
}

/** The Lichess rating Maia would play at for an opponent's rating, for the form. */
export function ratingQuery(rating: number, kind: RatingKind) {
  return queryOptions({
    queryKey: [...NOVELTY_KEY, "rating", rating, kind],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/novelty/rating", { params: { query: { rating, kind } } })),
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  });
}

/** A mutation that refreshes every novelty query when it succeeds. */
function useNoveltyMutation<In, Out>(mutationFn: (input: In) => Promise<Out>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: NOVELTY_KEY }),
  });
}

export function useStartSearch() {
  return useNoveltyMutation(async (body: NewSearch) =>
    unwrap(await api.POST("/api/v1/novelty/searches", { body })),
  );
}

export function useCancelSearch(searchId: number) {
  return useNoveltyMutation(async () =>
    unwrap(
      await api.POST("/api/v1/novelty/searches/{search_id}/cancel", {
        params: { path: { search_id: searchId } },
      }),
    ),
  );
}

export function useDeleteSearch(searchId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/api/v1/novelty/searches/{search_id}", {
        params: { path: { search_id: searchId } },
      });
      if (!response.ok) {
        throw new ApiError(response.status, problemDetail(error));
      }
    },
    // Only the list: the deleted search's own query would answer 404 now.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: searchesQuery.queryKey }),
  });
}
