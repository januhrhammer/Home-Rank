import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import { currentUserQuery } from "./currentUser";

export async function logOut(): Promise<void> {
  const { response } = await api.POST("/api/v1/auth/logout");
  if (!response.ok) {
    throw new ApiError(response.status);
  }
}

/**
 * Logs out and forgets everything cached for this user: on a shared computer, the next person
 * must not see the previous one's data.
 */
export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logOut,
    onSuccess: () => {
      // resetQueries, not removeQueries: both drop all cached data, but only reset tells the
      // components on screen. Otherwise a protected page could keep showing the old data.
      void queryClient.resetQueries();
      queryClient.setQueryData(currentUserQuery.queryKey, null);
    },
  });
}
