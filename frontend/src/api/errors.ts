/** A failed API call. `status` is the HTTP status, e.g. 429 for too many login attempts. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`API request failed with HTTP status ${String(status)}`);
    this.name = "ApiError";
    this.status = status;
  }
}
