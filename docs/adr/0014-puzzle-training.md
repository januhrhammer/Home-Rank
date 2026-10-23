# 14. Puzzles from the user's own games, trained with FSRS

Date: 2026-10-23

## Status

Accepted

## Context

Analysed games (ADR 0013) show where the user missed a chance, or where the opponent's blunder
gave them one. Those positions make the best training material: puzzles from the user's own
games, repeated until they stick. Spaced repetition schedules the repetitions; FSRS is the
current standard (used by Anki) and has a maintained Python package, `fsrs` (MIT licence).

## Decision

- **Finding puzzles** (`homerank.engine.tactics`, pure Python):
  - Candidates are positions on the user's turn that are clearly good for them (at least 66 %
    winning chances) where the opponent's last move gave away at least 20 percentage points
    (kind "found" if the user then played the engine's best move, "opponent_blunder" if not),
    or where the user's own move threw away at least 20 ("missed").
  - A candidate becomes a puzzle only if one move clearly wins: the engine compares the best
    two moves (multipv 2, deeper than the game's analysis) and the best must be at least 25
    points better. Mates count as the largest score, so a mating move is unique unless the
    second best also leaves a position won anyway (95 % or more).
  - The solution follows the engine's line, with the opponent's best replies, while the
    solver's move stays unique, up to 9 half-moves.
  - Themes for now: "mateInN" and "material" (at least two pawns won). The field takes more.
- **Data** (app `training`): `Puzzle` (one per game and position, with the position, the
  opponent's last move, the solution and themes), `PuzzleScan` (a game was searched),
  `ReviewCard` (the FSRS state of something to train, for now always a puzzle; repertoire moves
  will follow in M6) and `ReviewLog` (each review: rating, solved or not, time taken).
- **Scheduling**: the `fsrs` package with its default parameters and 90 % desired retention.
  A card's state is stored as the package's own dictionary, with its due time copied into a
  column for queries.
- **Rating a solve**: a wrong move is "Again"; solved, it is "Easy" at up to 5 seconds per move
  of the user's, "Good" up to 15, "Hard" beyond. The user can change the rating before the next
  puzzle.

## Consequences

- Searching games costs engine time like the analysis does, a few seconds per game, and runs
  in the same engine slots (ADR 0013).
- A user with many analysed games gets many puzzles at once; they come due in order of their
  creation.
- FSRS's parameters could later be fitted to each user's own review history; the logs are kept
  for that.
