import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { User } from "../features/auth";

/** What every test starts with: nobody is logged in. Any other request needs an answer. */
const defaultAnswers = [
  http.get("*/api/v1/auth/me", () => new HttpResponse(null, { status: 401 })),
];

/**
 * A simulated API for tests. Each test registers the answers it needs with server.use(...);
 * nothing ever reaches a real network.
 */
export const server = setupServer(...defaultAnswers);

/**
 * Simulates the auth API, remembering who is logged in like the server's session does.
 * Logging in always succeeds, as `user`.
 */
export function simulateAuth(user: User, { loggedIn = false } = {}) {
  let current: User | null = loggedIn ? user : null;
  server.use(
    http.get("*/api/v1/auth/me", () =>
      current ? HttpResponse.json(current) : new HttpResponse(null, { status: 401 }),
    ),
    http.get("*/api/v1/auth/csrf", () => new HttpResponse(null, { status: 204 })),
    http.post("*/api/v1/auth/login", () => {
      current = user;
      return HttpResponse.json(user);
    }),
    http.post("*/api/v1/auth/logout", () => {
      current = null;
      return new HttpResponse(null, { status: 204 });
    }),
  );
}
