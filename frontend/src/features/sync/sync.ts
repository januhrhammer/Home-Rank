import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components } from "../../api/schema";
import { t } from "../../lib/i18n";
import { settingsQuery } from "../settings";

export type LinkedAccount = components["schemas"]["LinkedAccountOut"];
export type SyncRun = components["schemas"]["SyncRunOut"];
export type Platform = LinkedAccount["platform"];
export type NewAccount = components["schemas"]["LinkedAccountIn"];

export const PLATFORMS: Platform[] = ["lichess", "chesscom"];

/** How often the list refreshes while a sync is waiting or running, in milliseconds. */
export const POLL_INTERVAL = 2000;

export function isActive(run: SyncRun | null): boolean {
  return run?.status === "queued" || run?.status === "running";
}

export async function fetchAccounts(): Promise<LinkedAccount[]> {
  const { data, response } = await api.GET("/api/v1/sync/accounts", {
    params: { query: { limit: 100 } },
  });
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data.items;
}

export const accountsQuery = queryOptions({
  queryKey: ["linked-accounts"],
  queryFn: fetchAccounts,
});

export function useAccounts() {
  return useQuery({
    ...accountsQuery,
    // Refresh while a sync is waiting or running, to show how far it got, and stop afterwards.
    refetchInterval: (query) =>
      query.state.data?.some((account) => isActive(account.last_run)) ? POLL_INTERVAL : false,
  });
}

/** Changes the list of accounts, then fetches it again. */
function useAccountMutation<T>(change: (variables: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountsQuery.queryKey }),
  });
}

export function useLinkAccount() {
  const queryClient = useQueryClient();
  return useAccountMutation(async (account: NewAccount) => {
    const { data, response } = await api.POST("/api/v1/sync/accounts", { body: account });
    if (data === undefined) {
      throw new ApiError(response.status);
    }
    // The username was added to the player names.
    await queryClient.invalidateQueries({ queryKey: settingsQuery.queryKey });
    return data;
  });
}

export function useSyncNow() {
  return useAccountMutation(async (accountId: number) => {
    const { data, response } = await api.POST("/api/v1/sync/accounts/{account_id}/sync", {
      params: { path: { account_id: accountId } },
    });
    if (data === undefined) {
      throw new ApiError(response.status);
    }
    return data;
  });
}

export function useSetEnabled() {
  return useAccountMutation(async ({ id, enabled }: { id: number; enabled: boolean }) => {
    const { data, response } = await api.PATCH("/api/v1/sync/accounts/{account_id}", {
      params: { path: { account_id: id } },
      body: { enabled },
    });
    if (data === undefined) {
      throw new ApiError(response.status);
    }
    return data;
  });
}

export function useUnlink() {
  return useAccountMutation(async (accountId: number) => {
    const { response } = await api.DELETE("/api/v1/sync/accounts/{account_id}", {
      params: { path: { account_id: accountId } },
    });
    if (!response.ok) {
      throw new ApiError(response.status);
    }
  });
}

/** Our own text for a failed link, so it can be translated (the server's text is English). */
export function linkErrorMessage(error: Error): string {
  if (error instanceof ApiError && error.status === 409) {
    return t("sync.taken");
  }
  if (error instanceof ApiError && error.status === 422) {
    return t("sync.invalidUsername");
  }
  return t("sync.linkFailed");
}
