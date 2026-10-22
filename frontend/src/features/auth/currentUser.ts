import { queryOptions, useQuery } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components } from "../../api/schema";

export type User = components["schemas"]["UserOut"];

/** The logged-in user, or null if nobody is logged in. */
export async function fetchCurrentUser(): Promise<User | null> {
  const { data, response } = await api.GET("/api/v1/auth/me");
  if (response.status === 401) {
    return null; // nobody logged in: a normal state, not an error
  }
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data;
}

/** The query for the logged-in user. Login and logout refresh what is cached under its key. */
export const currentUserQuery = queryOptions({
  queryKey: ["auth", "currentUser"],
  queryFn: fetchCurrentUser,
});

export function useCurrentUser() {
  return useQuery(currentUserQuery);
}
