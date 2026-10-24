# 18. Live engine analysis runs in the browser

Date: 2026-10-24

## Status

Accepted (maintainer, 2026-10-24)

## Context

M9 adds live analysis: Stockfish thinking about the position on the board, continuously, with
several lines, in the game viewer, the repertoire editor and the position search. It runs as
long as someone looks at a position, for every user at once.

Two places can run it:

- **The server's Stockfish**, its output streamed to the page. The website runs on gunicorn's
  synchronous workers (two by default): each open stream would hold one of them, so this needs
  an asynchronous server (ASGI) and a streaming protocol (server-sent events or WebSockets),
  and every viewer's analysis competes for the CPU of what is often a small home server.
- **Stockfish in the browser**, compiled to WebAssembly: [stockfish.js](https://github.com/nmrugg/stockfish.js)
  19 (Stockfish 19, GPL-3.0), which Lichess-style analysis boards use. Each user's own device
  does the work; the server only serves the files.

Measured on 2026-10-24 in Chromium (16-core desktop), 5 seconds on a middlegame position:

| Build | Download (gzipped) | Ready | Depth | Speed |
|---|---|---|---|---|
| lite, 1 thread | 1.2 MB | 0.08 s | 24 | 1.1 M nodes/s |
| lite, 4 threads | 1.2 MB | 0.46 s | 23 | 4.6 M nodes/s |
| full, 1 thread | 79 MB | 0.5 s | 22 | 0.6 M nodes/s |
| full, 4 threads | 79 MB | 0.9 s | 21 | 2.5 M nodes/s |

The full builds carry Stockfish's big neural network (99 MB, it barely compresses); the lite
builds a much smaller one: weaker per position, still far stronger than any human, and fast.
Threads need the page to be cross-origin isolated: the server sends
`Cross-Origin-Opener-Policy: same-origin` (Django's default already) and
`Cross-Origin-Embedder-Policy: require-corp`. Home-Rank loads nothing from other sites (fonts
and libraries are bundled, ADR 0010), so the second header costs nothing.

## Decision

- Live analysis runs **in the browser**, in a Web Worker, with stockfish.js's **lite**
  build: multi-threaded where the page is cross-origin isolated (up to the device's cores
  minus one, at most 4), single-threaded otherwise.
- The server sends `Cross-Origin-Embedder-Policy: require-corp` with every page, and Vite's
  dev server does the same.
- The engine files are served by Home-Rank itself, copied from the npm package at build time;
  the package's licence and a pointer to Stockfish's source go with them (GPL, ADR 0002).
- The background analysis of whole games stays on the server, with the full Stockfish
  (ADR 0013): it is what the stored evaluations, accuracies and puzzles come from.

## Consequences

- No server load for live analysis, however many users analyse; it even works while the
  server is busy analysing games.
- Weak phones analyse more slowly; the lines simply deepen more slowly.
- Live and stored evaluations can differ a little (different networks, different depths).
- If a user wants the full network later, its 99 MB download could be offered as an option.
