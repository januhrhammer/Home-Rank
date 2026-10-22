import createClient from "openapi-fetch";
import { afterEach, expect, test } from "vitest";

import { csrfMiddleware, readCookie } from "./client";
import type { paths } from "./schema";

/** A client like ours that records its requests instead of sending them. */
function recordingClient() {
  const requests: Request[] = [];
  const client = createClient<paths>({
    baseUrl: "http://localhost",
    fetch: (request) => {
      requests.push(request);
      return Promise.resolve(new Response(null, { status: 204 }));
    },
  });
  client.use(csrfMiddleware);
  return { client, requests };
}

afterEach(() => {
  for (const name of ["csrftoken", "theme"]) {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
  }
});

test("sends the CSRF token with state-changing requests", async () => {
  document.cookie = "csrftoken=token123";
  const { client, requests } = recordingClient();

  await client.POST("/api/v1/auth/logout");

  expect(requests[0]?.headers.get("X-CSRFToken")).toBe("token123");
});

test("does not send the CSRF token with reads", async () => {
  document.cookie = "csrftoken=token123";
  const { client, requests } = recordingClient();

  await client.GET("/api/v1/auth/me");

  expect(requests[0]?.headers.has("X-CSRFToken")).toBe(false);
});

test("reads one cookie among several and decodes it", () => {
  document.cookie = "theme=dark";
  document.cookie = "csrftoken=abc%3D";

  expect(readCookie("csrftoken")).toBe("abc=");
});
