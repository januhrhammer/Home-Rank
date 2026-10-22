// The account the tests log in with. `just e2e` creates it in the fresh database, with a new
// random password each run, and passes it on in these environment variables.

import path from "node:path";

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} isn't set: run the end-to-end tests with \`just e2e\`.`);
  }
  return value;
}

export const USERNAME = required("E2E_USERNAME");
export const PASSWORD = required("E2E_PASSWORD");

/** Where the login test saves the logged-in session (cookies) for the other tests. */
export const AUTH_FILE = path.join(import.meta.dirname, ".auth", "session.json");
