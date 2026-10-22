# 8. Recognising duplicate games

Date: 2026-10-22

## Status

Accepted

## Context

Users import the same games more than once: a PGN file exported twice, a tournament file that
contains games already synced from Lichess, an annotated copy of a game they already have.
Each game should be in the database once.

Synced games have an identity of their own, the platform and its game id, and are recognised
by that. Games from PGN files need a fingerprint computed from the game itself. What goes into
it decides what counts as "the same game":

- Too little, and different games merge: only the moves would make two short draws with the
  same moves one game.
- Too much, and copies slip through: Event and Site are spelled differently by different
  sources ("Casual game" or "?", "Hamburg" or "Hamburg GER"), and ECO or Opening headers are
  often missing.

Fingerprints are stored with each game, so changing what goes into them later means computing
them again for every game.

## Decision

A PGN game's fingerprint is the SHA-256 hash of:

- White and Black, normalised: case, Unicode composition and spaces don't count, so
  "Carlsen, Magnus" and "carlsen,magnus" are the same player;
- the date in PGN form, unknown parts included ("1960.??.??");
- the result;
- the starting position (for Chess960 and set-up positions);
- the main line's moves.

Comments, variations and NAGs don't count, and neither do the other headers. A version number
is part of the hash, so that a future change can be told apart from today's fingerprints.

Implemented in `homerank.chesslib.dedup`; a test pins the fingerprint of one game, so the
definition can't change by accident.

## Consequences

- Importing an annotated copy of a game that is already in the database skips it as a
  duplicate: the first copy's text is kept. Editing the stored game, which comes after M1, is
  the way to add annotations to it.
- A game whose date differs between sources (for example, a game played around midnight with
  the date in two time zones) is imported twice.
- Changing the definition means raising the version and recomputing all fingerprints in a data
  migration.
