import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

// Cross-origin isolation, as the server sends it (backend/homerank/core/isolation.py), so the
// engine may use several threads in development too.
const ISOLATION = {
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Embedder-Policy": "require-corp",
};

/**
 * Stockfish for live analysis (ADR 0018): the npm package's lite builds, served at /engine/.
 * The multi-threaded build for cross-origin isolated pages, the single-threaded one otherwise;
 * each .js loads the .wasm of the same name next to it. Its licence (GPL) goes along, with a
 * note on where its source is.
 */
const ENGINE_FILES = [
  "bin/stockfish-19-lite.js",
  "bin/stockfish-19-lite.wasm",
  "bin/stockfish-19-lite-single.js",
  "bin/stockfish-19-lite-single.wasm",
  "Copying.txt",
];
const ENGINE_SOURCE = `Stockfish 19, compiled to WebAssembly by stockfish.js (npm: stockfish@19.0.1),
licensed under the GNU GPL 3.0 (Copying.txt).

Source: https://github.com/official-stockfish/Stockfish
        https://github.com/nmrugg/stockfish.js
`;

function engineFiles(): Plugin {
  const packageDir = path.dirname(createRequire(import.meta.url).resolve("stockfish/package.json"));
  const files = new Map(ENGINE_FILES.map((file) => [path.basename(file), file]));
  return {
    name: "home-rank-engine-files",
    // The dev server answers /engine/<file> from the package.
    configureServer(server) {
      server.middlewares.use("/engine", (request, response, next) => {
        const file = files.get((request.url ?? "").replace(/^\//, ""));
        if (file === undefined) {
          next();
          return;
        }
        const type = file.endsWith(".wasm") ? "application/wasm" : "text/javascript";
        response.setHeader("Content-Type", file.endsWith(".txt") ? "text/plain" : type);
        // The worker's own script needs the isolation headers too, or the browser refuses it.
        for (const [name, value] of Object.entries(ISOLATION)) {
          response.setHeader(name, value);
        }
        response.end(readFileSync(path.join(packageDir, file)));
      });
    },
    // The build puts them into dist/engine/, which the server serves like the other files.
    generateBundle() {
      for (const [name, file] of files) {
        const source = readFileSync(path.join(packageDir, file));
        this.emitFile({ type: "asset", fileName: `engine/${name}`, source });
      }
      this.emitFile({ type: "asset", fileName: "engine/SOURCE.txt", source: ENGINE_SOURCE });
    },
  };
}

export default defineConfig({
  plugins: [react(), engineFiles()],
  server: {
    port: 5173,
    // Fail if the port is taken instead of quietly moving to another one.
    strictPort: true,
    headers: ISOLATION,
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
  preview: { headers: ISOLATION },
  test: {
    // A simulated browser in Node: fast, and close enough for component tests.
    environment: "jsdom",
    // Only the unit tests: e2e/ holds Playwright's tests, which `just e2e` runs.
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test/setup.ts"],
  },
});
