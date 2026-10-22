import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { ApiError } from "../../api/errors";
import { server } from "../../test/server";
import { fetchCurrentUser, type User } from "./currentUser";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

test("returns the logged-in user", async () => {
  server.use(http.get("*/api/v1/auth/me", () => HttpResponse.json(alice)));

  await expect(fetchCurrentUser()).resolves.toEqual(alice);
});

test("returns null when nobody is logged in", async () => {
  server.use(http.get("*/api/v1/auth/me", () => new HttpResponse(null, { status: 401 })));

  await expect(fetchCurrentUser()).resolves.toBeNull();
});

test("fails with the HTTP status on other errors", async () => {
  server.use(http.get("*/api/v1/auth/me", () => new HttpResponse(null, { status: 500 })));

  await expect(fetchCurrentUser()).rejects.toThrow(new ApiError(500));
});
