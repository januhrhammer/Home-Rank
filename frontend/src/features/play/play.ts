import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError, problemDetail } from "../../api/errors";
import type { components } from "../../api/schema";

export type BotGame = components["schemas"]["BotGameOut"];
export type NewGame = components["schemas"]["GameIn"];
export type Opponent = components["schemas"]["Opponent"];
export type OpponentRange = components["schemas"]["OpponentOut"];

/** The start of every play query's key, to refresh them all after a change. */
export const PLAY_KEY = ["play"] as const;

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

export const opponentsQuery = queryOptions({
  queryKey: [...PLAY_KEY, "opponents"],
  queryFn: async () => unwrap(await api.GET("/api/v1/play/opponents")),
  staleTime: Infinity, // the bots' ranges come with the server's version
});

/** The list of games. Its key starts each game's key too: refresh it with `exact: true`, or
 * every game on screen is fetched again (and a move's answer overwritten by an older state). */
export const gamesQuery = queryOptions({
  queryKey: [...PLAY_KEY, "games"],
  queryFn: async () => unwrap(await api.GET("/api/v1/play/games")),
});

export function gameQuery(gameId: number) {
  return queryOptions({
    queryKey: [...PLAY_KEY, "games", gameId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/play/games/{game_id}", {
          params: { path: { game_id: gameId } },
        }),
      ),
    // The game changes only through this page's own moves, which bring its new state; a
    // refetch on focus would only reset the running clock to the server's view.
    refetchOnWindowFocus: false,
  });
}

/** A change to one game: the answer is the game's new state, shown at once. */
function useGameMutation<In>(gameId: number, request: (input: In) => Promise<BotGame>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: (game) => {
      queryClient.setQueryData(gameQuery(gameId).queryKey, game);
      void queryClient.invalidateQueries({ queryKey: gamesQuery.queryKey, exact: true });
    },
  });
}

const path = (gameId: number) => ({ params: { path: { game_id: gameId } } });

export function useStartGame() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: NewGame) => unwrap(await api.POST("/api/v1/play/games", { body })),
    onSuccess: (game) => {
      queryClient.setQueryData(gameQuery(game.id).queryKey, game);
      void queryClient.invalidateQueries({ queryKey: gamesQuery.queryKey, exact: true });
    },
  });
}

export function usePlayMove(gameId: number) {
  return useGameMutation(gameId, async (moveUci: string) =>
    unwrap(
      await api.POST("/api/v1/play/games/{game_id}/moves", {
        ...path(gameId),
        body: { move_uci: moveUci },
      }),
    ),
  );
}

export function useTakeBack(gameId: number) {
  return useGameMutation(gameId, async () =>
    unwrap(await api.POST("/api/v1/play/games/{game_id}/take-back", path(gameId))),
  );
}

export function useResign(gameId: number) {
  return useGameMutation(gameId, async () =>
    unwrap(await api.POST("/api/v1/play/games/{game_id}/resign", path(gameId))),
  );
}

/** Add the game to the user's games; the game then knows its copy. */
export function useSaveGame(gameId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/v1/play/games/{game_id}/save", path(gameId))),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PLAY_KEY }),
  });
}

export function useDeleteGame() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (gameId: number) => {
      const { response, error } = await api.DELETE("/api/v1/play/games/{game_id}", path(gameId));
      if (!response.ok) {
        throw new ApiError(response.status, problemDetail(error));
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: gamesQuery.queryKey, exact: true }),
  });
}
