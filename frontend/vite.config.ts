import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Fail if the port is taken instead of quietly moving to another one.
    strictPort: true,
    proxy: {
      // The browser only talks to this dev server, so API calls are same-origin, as in
      // production.
      "/api": {
        target: "http://localhost:8100",
        // Keep the browser's Host header (localhost:5173): Django's CSRF check compares it
        // with the Origin header. Vite's short form ("/api": "http://...") would rewrite it.
        changeOrigin: false,
      },
    },
  },
  test: {
    // A simulated browser in Node: fast, and close enough for component tests.
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
