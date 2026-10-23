// Runs before every test file (see test.setupFiles in vite.config.ts).
import "@testing-library/jest-dom/vitest"; // matchers such as toBeInTheDocument()

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, vi } from "vitest";

import { server } from "./server";

// jsdom lays nothing out, so it lacks scrolling; components may still ask for it.
Element.prototype.scrollIntoView = () => undefined;

// Nor does it know media queries: none matches, as on a plain desktop browser. (The board asks
// whether the system prefers reduced motion.)
window.matchMedia = (query: string) =>
  ({
    matches: false,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }) as unknown as MediaQueryList;

// A request without a registered answer fails the test instead of going out to the network.
// (MSW's default only warns and then lets the request through.)
beforeAll(() => {
  server.listen({ onUnhandledFrame: "error" });
});

// Remove what each test rendered, so tests can't see each other's output. Testing Library does
// this by itself only when Vitest's global functions are enabled; we import them explicitly.
// Also forget the answers the test registered, and what it stored in the browser.
afterEach(() => {
  cleanup();
  server.resetHandlers();
  vi.restoreAllMocks(); // e.g. the fetch that answerUploads() replaces
  localStorage.clear(); // e.g. the viewer's notation
});

afterAll(async () => {
  server.close();
  // React Aria announces some changes to screen readers 100 ms late when Testing Library is
  // waiting (findBy…, waitFor). Let such an announcement happen before jsdom goes away, or it
  // fails the run with "document is not defined".
  await new Promise((resolve) => setTimeout(resolve, 150));
});
