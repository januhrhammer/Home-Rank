import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components } from "../../api/schema";
import { t } from "../../lib/i18n";

export type Import = components["schemas"]["ImportOut"];

/** How often the list refreshes while an import is waiting or running, in milliseconds. */
export const POLL_INTERVAL = 1000;

export function isActive(run: Import): boolean {
  return run.status === "queued" || run.status === "running";
}

/** The user's latest imports, the newest first. */
export async function fetchImports(): Promise<Import[]> {
  const { data, response } = await api.GET("/api/v1/games/imports", {
    params: { query: { limit: 20 } },
  });
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data.items;
}

export const importsQuery = queryOptions({ queryKey: ["imports"], queryFn: fetchImports });

export function useImports() {
  return useQuery({
    ...importsQuery,
    // Refresh to show the progress while an import is waiting or running, and stop afterwards.
    refetchInterval: (query) => (query.state.data?.some(isActive) ? POLL_INTERVAL : false),
  });
}

export async function uploadPgn(file: File): Promise<Import> {
  const { data, response } = await api.POST("/api/v1/games/imports", {
    // OpenAPI describes a file as a string, so that is what the types expect here. What is sent
    // is the FormData that bodySerializer builds, with the file itself.
    body: { file: file.name },
    bodySerializer: () => {
      const form = new FormData();
      form.append("file", file);
      return form;
    },
  });
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data;
}

/** Uploads a PGN file, then refreshes the list, which starts showing the import's progress. */
export function useUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: uploadPgn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: importsQuery.queryKey }),
  });
}

/** Our own text for a failed upload, so it can be translated (the server's text is English). */
export function uploadErrorMessage(error: Error): string {
  if (error instanceof ApiError && error.status === 413) {
    return t("import.tooLarge");
  }
  if (error instanceof ApiError && error.status === 415) {
    return t("import.wrongType");
  }
  return t("import.uploadFailed");
}
