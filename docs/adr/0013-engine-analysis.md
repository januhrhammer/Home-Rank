# 13. Engine analysis of games

Date: 2026-10-23

## Status

Accepted

## Context

Home-Rank analyses the user's games with Stockfish (ADR 0012) to show an evaluation per
position, mark inaccuracies, mistakes and blunders, and give each player an accuracy, and later
to find puzzles in the user's own mistakes (M4). Analysis is slow: a game of 80 positions at
depth 18 takes some seconds to a minute, depending on the machine, and a homeserver may be a
Raspberry Pi. Players know these numbers from Lichess, so they should mean the same here.

## Decision

- **Data** (app `analysis`):
  - `PositionEval`, one row per position of a game's main line (key: game and ply, as
    `games.GamePosition`): depth, score in centipawns or moves to mate, from White's point of
    view, White's winning chances, best move, the engine's line (first 10 moves) and the engine
    name. Analysing again only replaces a position with a result at least as deep: the deepest
    result stays.
  - `GameAnalysis`, one per analysed game: each player's accuracy, the shallowest depth and the
    engine, so lists can show whether and how deeply a game was analysed.
  - `AnalysisRun`, one per analysis job, with progress (positions done of total), like file
    imports and syncs.
  - `AnalysisSettings`, one per user (the defaults while there is none): whether to analyse new
    games automatically, and the thresholds for inaccuracies, mistakes and blunders.
- **Numbers as on Lichess** (`homerank.engine.evaluation`): winning chances by Lichess's
  formula (scores capped at ±10 pawns, a mate counts as the cap), moves classified by the
  winning chances they lose (10 / 20 / 30 percentage points by default, per user), Lichess's
  accuracy formula. Checked against three games analysed on Lichess: same accuracies.
- Winning chances are stored, not only the score: a checkmated position's "mate 0" needs the
  side to move to say who won, which only the analysis knows. Classifications are computed when
  read, because each user may choose their own thresholds; accuracy doesn't depend on them and
  is stored.
- Only the main line is analysed (multipv 1), as the specification asks for game analysis.

## Consequences

- One `PositionEval` row per position: about 80 rows per game, the same as `GamePosition`.
- Changing the thresholds reclassifies all moves at once, with no job.
- The engine's settings (threads, hash, depth, quiet hours, how many games at once) belong to
  the server, not to users; they come with the analysis jobs.
