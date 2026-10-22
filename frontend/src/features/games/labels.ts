/**
 * Tags and collections: creating, changing and deleting them, and adding or removing a game.
 * Both work the same way, so the functions take the kind as their first argument.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import { t } from "../../lib/i18n";
import { collectionsQuery, GAMES_KEY, tagsQuery } from "./games";

export type LabelKind = "tags" | "collections";

function check(response: Response) {
  if (!response.ok) {
    throw new ApiError(response.status);
  }
}

export interface LabelFields {
  name: string;
  /** Collections only. */
  description?: string;
}

export async function createLabel(kind: LabelKind, fields: LabelFields) {
  const { data, response } =
    kind === "tags"
      ? await api.POST("/api/v1/tags", { body: { name: fields.name } })
      : await api.POST("/api/v1/collections", {
          body: { name: fields.name, description: fields.description ?? "" },
        });
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data;
}

async function updateLabel(kind: LabelKind, id: number, fields: LabelFields) {
  const { response } =
    kind === "tags"
      ? await api.PATCH("/api/v1/tags/{tag_id}", {
          params: { path: { tag_id: id } },
          body: { name: fields.name },
        })
      : await api.PATCH("/api/v1/collections/{collection_id}", {
          params: { path: { collection_id: id } },
          body: fields,
        });
  check(response);
}

async function deleteLabel(kind: LabelKind, id: number) {
  const { response } =
    kind === "tags"
      ? await api.DELETE("/api/v1/tags/{tag_id}", { params: { path: { tag_id: id } } })
      : await api.DELETE("/api/v1/collections/{collection_id}", {
          params: { path: { collection_id: id } },
        });
  check(response);
}

/** Afterwards, everything that shows labels loads again: the lists, games, the game list. */
function useRefresh(kind: LabelKind) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({
        queryKey: kind === "tags" ? tagsQuery.queryKey : collectionsQuery.queryKey,
      }),
      queryClient.invalidateQueries({ queryKey: GAMES_KEY }),
    ]);
}

export function useCreateLabel(kind: LabelKind) {
  const refresh = useRefresh(kind);
  return useMutation({
    mutationFn: (fields: LabelFields) => createLabel(kind, fields),
    onSuccess: refresh,
  });
}

export function useUpdateLabel(kind: LabelKind, id: number) {
  const refresh = useRefresh(kind);
  return useMutation({
    mutationFn: (fields: LabelFields) => updateLabel(kind, id, fields),
    onSuccess: refresh,
  });
}

export function useDeleteLabel(kind: LabelKind, id: number) {
  const refresh = useRefresh(kind);
  return useMutation({ mutationFn: () => deleteLabel(kind, id), onSuccess: refresh });
}

/** Our own words for a failed change; 409 means the name is taken. */
export function labelErrorMessage(error: Error, name: string): string {
  if (error instanceof ApiError && error.status === 409) {
    return t("labels.taken", { name });
  }
  return t("labels.failed");
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
  const refresh = useRefresh(kind);
  return useMutation({
    mutationFn: async (change: LabelChange) => {
      if (change.action === "remove") {
        await removeGame(kind, change.labelId, gameId);
        return;
      }
      const labelId =
        change.action === "add"
          ? change.labelId
          : (await createLabel(kind, { name: change.name })).id;
      await addGame(kind, labelId, gameId);
    },
    onSettled: refresh,
  });
}
