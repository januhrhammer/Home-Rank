/**
 * Tags and collections of a single game: adding, removing, and creating new ones on the way.
 * Both work the same way, so the functions take the kind as their first argument.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import { collectionsQuery, GAMES_KEY, type NamedRef, tagsQuery } from "./games";

export type LabelKind = "tags" | "collections";

function check(response: Response) {
  if (!response.ok) {
    throw new ApiError(response.status);
  }
}

async function createLabel(kind: LabelKind, name: string): Promise<NamedRef> {
  const { data, response } =
    kind === "tags"
      ? await api.POST("/api/v1/tags", { body: { name } })
      : await api.POST("/api/v1/collections", { body: { name, description: "" } });
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data;
}

async function addGame(kind: LabelKind, labelId: number, gameId: number) {
  const body = { game_ids: [gameId] };
  const { response } =
    kind === "tags"
      ? await api.POST("/api/v1/tags/{tag_id}/games", {
          params: { path: { tag_id: labelId } },
          body,
        })
      : await api.POST("/api/v1/collections/{collection_id}/games", {
          params: { path: { collection_id: labelId } },
          body,
        });
  check(response);
}

async function removeGame(kind: LabelKind, labelId: number, gameId: number) {
  const query = { game_ids: [gameId] };
  const { response } =
    kind === "tags"
      ? await api.DELETE("/api/v1/tags/{tag_id}/games", {
          params: { path: { tag_id: labelId }, query },
        })
      : await api.DELETE("/api/v1/collections/{collection_id}/games", {
          params: { path: { collection_id: labelId }, query },
        });
  check(response);
}

export type LabelChange =
  | { action: "add"; labelId: number }
  | { action: "create"; name: string }
  | { action: "remove"; labelId: number };

/** Changes a game's tags or collections, then refreshes what shows them: games and the lists. */
export function useLabelChange(kind: LabelKind, gameId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (change: LabelChange) => {
      if (change.action === "remove") {
        await removeGame(kind, change.labelId, gameId);
        return;
      }
      const labelId =
        change.action === "add" ? change.labelId : (await createLabel(kind, change.name)).id;
      await addGame(kind, labelId, gameId);
    },
    onSettled: async () => {
      const labels = kind === "tags" ? tagsQuery : collectionsQuery;
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: GAMES_KEY }),
        queryClient.invalidateQueries({ queryKey: labels.queryKey }),
      ]);
    },
  });
}
