import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./schema";

const CSRF_COOKIE = "csrftoken";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

export function readCookie(name: string): string | undefined {
  const cookie = document.cookie.split("; ").find((entry) => entry.startsWith(`${name}=`));
  return cookie === undefined ? undefined : decodeURIComponent(cookie.slice(name.length + 1));
}

/** Django rejects state-changing requests that don't repeat the CSRF cookie in a header. */
export const csrfMiddleware: Middleware = {
  onRequest({ request }) {
    const token = readCookie(CSRF_COOKIE);
    if (!SAFE_METHODS.has(request.method) && token !== undefined) {
      request.headers.set("X-CSRFToken", token);
    }
    return request;
  },
};

/**
 * The typed API client. Paths, parameters, request bodies and responses are checked against
 * schema.d.ts, which `just gen-api` generates from the backend.
 */
export const api = createClient<paths>();
api.use(csrfMiddleware);
