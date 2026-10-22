import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components } from "../../api/schema";
import { t } from "../../lib/i18n";
import { currentUserQuery, type User } from "./currentUser";

export type Credentials = components["schemas"]["LoginIn"];

export async function logIn(credentials: Credentials): Promise<User> {
  // Django sets the CSRF cookie only when asked, and login is rejected without it.
  await api.GET("/api/v1/auth/csrf");
  const { data, response } = await api.POST("/api/v1/auth/login", { body: credentials });
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data;
}

/** Logs in and stores the user as the logged-in user, so every component knows at once. */
export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logIn,
    onSuccess: (user) => {
      queryClient.setQueryData(currentUserQuery.queryKey, user);
    },
  });
}

/** Our own text for a failed login, so it can be translated (the server's text is English). */
export function loginErrorMessage(error: Error): string {
  if (error instanceof ApiError && error.status === 401) {
    return t("login.invalidCredentials");
  }
  if (error instanceof ApiError && error.status === 429) {
    return t("login.tooManyAttempts");
  }
  return t("login.failed");
}
