# 21. Opening names from Lichess's opening list, looked up by position

Date: 2026-10-25

## Status

Accepted (maintainer, 2026-10-25)

## Context

Games show their opening by the PGN's `ECO` and `Opening` headers. Many files have only the ECO
code: Lumbra's GigaBase (14 million games on the maintainer's server), Chess.com's games and most
tournament files. "B90" says little; the maintainer asked for the opening's name.

Lichess publishes its opening list as public domain (CC0,
[lichess-org/chess-openings](https://github.com/lichess-org/chess-openings)): 3,865 named
openings in five TSV files (ECO, name, moves; 395 KB), e.g. "Sicilian Defense: Najdorf
Variation, English Attack". Lichess names games by it, by position.

Two ways to use it were considered:

- **Name games on import** and store the name: every game would need its moves replayed again,
  the 14 million games already imported a re-import or a backfill of hours, and a newer list
  would need the same again.
- **Look the name up when a game is shown**, from the positions its moves reach: building the
  lookup table takes 0.24 s once per process; a page of 50 games replays at most 40 half-moves
  each, a few milliseconds.

## Decision

- The five TSV files are part of the repository (`backend/homerank/chesslib/data/openings/`),
  at a fixed version of Lichess's list, with a note naming it and its licence. A script fetches a
  newer version and checks it; nothing is downloaded at runtime.
- `homerank.chesslib.openings` (no Django) builds, once per process, a table from each opening's
  final position (its Polyglot hash, as the app's position index uses) to its ECO code and name.
  A game's opening is the **last named position** among its first 40 half-moves, so a
  transposition gets the name of the position it reaches.
- Shown name: the looked-up name; else the PGN's `Opening` header; else only the ECO code. The
  ECO code shown is the looked-up one when there is a name.
- Where: the lists and pages of the user's games and of reference games, and the opening explorer
  (the name of the position on the board). Nothing is stored; the API adds the name to what it
  returns.

## Consequences

- No re-import and no schema change; a newer list applies once the server restarts.
- Lichess games keep their names (same list); Chess.com games and OTB files get names.
- Filters by opening still work on the stored headers only (ECO prefix); filtering by looked-up
  name would need it stored, if wanted later.
- The list's names are English, as the app is.
