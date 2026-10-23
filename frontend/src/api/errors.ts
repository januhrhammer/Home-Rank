/** A failed API call. `status` is the HTTP status, e.g. 429 for too many login attempts. */
export class ApiError extends Error {
  readonly status: number;
  /** The server's explanation, if it sent one; written to be shown to users. */
  readonly detail: string | undefined;

  constructor(status: number, detail?: string) {
    super(`API request failed with HTTP status ${String(status)}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** The detail of a problem response (RFC 9457), as the API sends with every error. */
export function problemDetail(body: unknown): string | undefined {
  if (typeof body === "object" && body !== null && "detail" in body) {
    return typeof body.detail === "string" ? body.detail : undefined;
  }
  return undefined;
}
