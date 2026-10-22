import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components } from "../../api/schema";

export type Settings = components["schemas"]["SettingsOut"];
export type SettingsChanges = components["schemas"]["SettingsPatch"];

export async function fetchSettings(): Promise<Settings> {
  const { data, response } = await api.GET("/api/v1/settings");
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data;
}

export const settingsQuery = queryOptions({ queryKey: ["settings"], queryFn: fetchSettings });

export async function saveSettings(changes: SettingsChanges): Promise<Settings> {
  const { data, response } = await api.PATCH("/api/v1/settings", { body: changes });
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data;
}

/** Saves changes and keeps the server's answer, e.g. the names as it tidied them. */
export function useSaveSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveSettings,
    onSuccess: (settings) => {
      queryClient.setQueryData(settingsQuery.queryKey, settings);
    },
  });
}
