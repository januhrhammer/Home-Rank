import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    // A simulated browser in Node: fast, and close enough for component tests.
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
