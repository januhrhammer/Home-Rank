import { setupServer } from "msw/node";

/**
 * A simulated API for tests. Each test registers the answers it needs with server.use(...);
 * nothing ever reaches a real network.
 */
export const server = setupServer();
