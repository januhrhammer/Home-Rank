import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError, problemDetail } from "../../api/errors";
import type { components } from "../../api/schema";

export type Repertoire = components["schemas"]["RepertoireOut"];
export type RepertoireMove = components["schemas"]["MoveOut"];
export type PgnImport = components["schemas"]["PgnImportOut"];
export type RepertoireLine = components["schemas"]["LineOut"];
export type Color = Repertoire["color"];

/** The start of every repertoire query's key, to refresh them all after a change. */
export const REPERTOIRE_KEY = ["repertoires"] as const;

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

export const repertoiresQuery = queryOptions({
  queryKey: [...REPERTOIRE_KEY, "list"],
  queryFn: async () => unwrap(await api.GET("/api/v1/repertoires")),
});

export function repertoireQuery(repertoireId: number) {
  return queryOptions({
    queryKey: [...REPERTOIRE_KEY, repertoireId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/repertoires/{repertoire_id}", {
          params: { path: { repertoire_id: repertoireId } },
        }),
      ),
  });
}

export function movesQuery(repertoireId: number) {
  return queryOptions({
    queryKey: [...REPERTOIRE_KEY, repertoireId, "moves"],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/repertoires/{repertoire_id}/moves", {
          params: { path: { repertoire_id: repertoireId } },
        }),
      ),
  });
}

export function linesQuery(repertoireId: number) {
  return queryOptions({
    queryKey: [...REPERTOIRE_KEY, repertoireId, "lines"],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/repertoires/{repertoire_id}/lines", {
          params: { path: { repertoire_id: repertoireId } },
        }),
      ),
  });
}

/** A mutation that refreshes every repertoire query when it succeeds. */
function useRepertoireMutation<In, Out>(mutationFn: (input: In) => Promise<Out>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: REPERTOIRE_KEY }),
  });
}

export function useCreateRepertoire() {
  return useRepertoireMutation(async (body: { name: string; color: Color }) =>
    unwrap(await api.POST("/api/v1/repertoires", { body })),
  );
}

export function useRenameRepertoire(repertoireId: number) {
  return useRepertoireMutation(async (name: string) =>
    unwrap(
      await api.PATCH("/api/v1/repertoires/{repertoire_id}", {
        params: { path: { repertoire_id: repertoireId } },
        body: { name },
      }),
    ),
  );
}

export function useDeleteRepertoire(repertoireId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/api/v1/repertoires/{repertoire_id}", {
        params: { path: { repertoire_id: repertoireId } },
      });
      if (!response.ok) {
        throw new ApiError(response.status, problemDetail(error));
      }
    },
    // Only the list: the deleted repertoire's own queries would answer 404 now.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: repertoiresQuery.queryKey }),
  });
}

export function useCreateLine(repertoireId: number) {
  return useRepertoireMutation(async (name: string) =>
    unwrap(
      await api.POST("/api/v1/repertoires/{repertoire_id}/lines", {
        params: { path: { repertoire_id: repertoireId } },
        body: { name },
      }),
    ),
  );
}

export function useRenameLine(repertoireId: number, lineId: number) {
  return useRepertoireMutation(async (name: string) =>
    unwrap(
      await api.PATCH("/api/v1/repertoires/{repertoire_id}/lines/{line_id}", {
        params: { path: { repertoire_id: repertoireId, line_id: lineId } },
        body: { name },
      }),
    ),
  );
}

export function useReorderLines(repertoireId: number) {
  return useRepertoireMutation(async (lineIds: number[]) =>
    unwrap(
      await api.PUT("/api/v1/repertoires/{repertoire_id}/lines/order", {
        params: { path: { repertoire_id: repertoireId } },
        body: { line_ids: lineIds },
      }),
    ),
  );
}

export function useDeleteLine(repertoireId: number, lineId: number) {
  return useRepertoireMutation(async () =>
    unwrap(
      await api.DELETE("/api/v1/repertoires/{repertoire_id}/lines/{line_id}", {
        params: { path: { repertoire_id: repertoireId, line_id: lineId } },
      }),
    ),
  );
}

/** Add a move to a line; without one (e.g. from the gap report), to the first line that
 * reaches the position. */
export function useAddMove(repertoireId: number) {
  return useRepertoireMutation(async (body: { fen: string; move_uci: string; line_id?: number }) =>
    unwrap(
      await api.POST("/api/v1/repertoires/{repertoire_id}/moves", {
        params: { path: { repertoire_id: repertoireId } },
        body,
      }),
    ),
  );
}

export function useCommentMove(repertoireId: number) {
  return useRepertoireMutation(async ({ moveId, comment }: { moveId: number; comment: string }) =>
    unwrap(
      await api.PATCH("/api/v1/repertoires/{repertoire_id}/moves/{move_id}", {
        params: { path: { repertoire_id: repertoireId, move_id: moveId } },
        body: { comment },
      }),
    ),
  );
}

/** Take a move out of one line, with the moves that line reached only through it. */
export function useRemoveMove(repertoireId: number) {
  return useRepertoireMutation(async ({ moveId, lineId }: { moveId: number; lineId: number }) =>
    unwrap(
      await api.DELETE("/api/v1/repertoires/{repertoire_id}/moves/{move_id}", {
        params: {
          path: { repertoire_id: repertoireId, move_id: moveId },
          query: { line_id: lineId },
        },
      }),
    ),
  );
}

export function useImportPgn(repertoireId: number) {
  return useRepertoireMutation(async (file: File) =>
    unwrap(
      await api.POST("/api/v1/repertoires/{repertoire_id}/import", {
        params: { path: { repertoire_id: repertoireId } },
        // OpenAPI describes a file as a string, so that is what the types expect here. What is
        // sent is the FormData that bodySerializer builds, with the file itself.
        body: { file: file.name },
        bodySerializer: () => {
          const form = new FormData();
          form.append("file", file);
          return form;
        },
      }),
    ),
  );
}

export function useSeed(repertoireId: number) {
  return useRepertoireMutation(async (body: { depth: number; min_games: number }) =>
    unwrap(
      await api.POST("/api/v1/repertoires/{repertoire_id}/seed", {
        params: { path: { repertoire_id: repertoireId } },
        body,
      }),
    ),
  );
}
