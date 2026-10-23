import { queryOptions, useMutation } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components } from "../../api/schema";

export type ExplorerData = components["schemas"]["ExplorerOut"];
export type MoveStats = components["schemas"]["MoveStatsOut"];
export type ReferenceDatabase = components["schemas"]["ReferenceDatabaseOut"];
export type ReferenceGameItem = components["schemas"]["ReferenceGameItem"];
export type ReferenceGame = components["schemas"]["ReferenceGameOut"];
export type MySearch = components["schemas"]["MySearchOut"];
export type ReferenceSearch = components["schemas"]["ReferenceSearchOut"];

/** Where explorer statistics and search results come from: your games or a reference database. */
export type Source = { kind: "mine" } | { kind: "reference"; databaseId: number };

function unwrap<T>({ data, response }: { data?: T; response: Response }): T {
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data;
}

export const databasesQuery = queryOptions({
  queryKey: ["reference-databases"],
  queryFn: async () => unwrap(await api.GET("/api/v1/reference/databases")),
});

export function explorerQuery(source: Source, fen: string) {
  return queryOptions({
    queryKey: ["explorer", source, fen],
    queryFn: async () =>
      source.kind === "mine"
        ? unwrap(await api.GET("/api/v1/explorer/my", { params: { query: { fen } } }))
        : unwrap(
            await api.GET("/api/v1/explorer/reference/{database_id}", {
              params: { path: { database_id: source.databaseId }, query: { fen } },
            }),
          ),
    staleTime: 60_000, // statistics change only with imports
  });
}

export function mySearchQuery(fen: string, page: number) {
  return queryOptions({
    queryKey: ["search", "mine", fen, page],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/explorer/search/my", { params: { query: { fen, page } } })),
  });
}

export function referenceSearchQuery(databaseId: number, fen: string, page: number) {
  return queryOptions({
    queryKey: ["search", databaseId, fen, page],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/explorer/search/reference/{database_id}", {
          params: { path: { database_id: databaseId }, query: { fen, page } },
        }),
      ),
  });
}

export function referenceGamesQuery(
  databaseId: number,
  filters: { player?: string; eco?: string; min_rating?: number },
  offset: number,
) {
  return queryOptions({
    queryKey: ["reference-games", databaseId, filters, offset],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/reference/databases/{database_id}/games", {
          params: { path: { database_id: databaseId }, query: { ...filters, limit: 50, offset } },
        }),
      ),
  });
}

export function referenceGameQuery(databaseId: number, gameId: number) {
  return queryOptions({
    queryKey: ["reference-game", databaseId, gameId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/reference/databases/{database_id}/games/{game_id}", {
          params: { path: { database_id: databaseId, game_id: gameId } },
        }),
      ),
  });
}

/** Copies a reference game into the user's games; returns the id of their copy. */
export function useCopyGame(databaseId: number, gameId: number) {
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/reference/databases/{database_id}/games/{game_id}/copy", {
          params: { path: { database_id: databaseId, game_id: gameId } },
          body: {},
        }),
      ),
  });
}

/** White's score in percent after a move: wins count 1, draws 1/2. */
export function whiteScore(move: MoveStats): number {
  const decided = move.white + move.draws + move.black;
  return decided === 0 ? 50 : Math.round(((move.white + move.draws / 2) / decided) * 100);
}
