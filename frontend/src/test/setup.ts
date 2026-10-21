// Runs before every test file (see test.setupFiles in vite.config.ts).
import "@testing-library/jest-dom/vitest"; // matchers such as toBeInTheDocument()

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Remove what each test rendered, so tests can't see each other's output. Testing Library does
// this by itself only when Vitest's global functions are enabled; we import them explicitly.
afterEach(() => {
  cleanup();
});
