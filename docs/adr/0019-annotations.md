# 19. Annotations change a game's PGN, never its main line

Date: 2026-10-24

## Status

Proposed

## Context

M9 lets users annotate their games in the viewer: comments, variations, move marks (!, ?, !?,
?!, !!, ??) and position marks (+−, =, …). A game is stored as its PGN text (`Game.pgn`), with
derived data: its fingerprint for duplicates (ADR 0008), its positions for search and the
explorer (`GamePosition`, main line only), and its engine analysis per ply of the main line
(`PositionEval`, ADR 0013). The fingerprint already ignores comments, variations and NAGs.

## Decision

- Annotations **never change the main line**: they add, edit or remove comments, NAGs and
  variations. Fingerprint, positions and analysis stay valid without recomputing anything.
  (Promoting a variation to the main line, or editing moves, would make it another game; not
  offered.)
- The PGN stays the record. The viewer edits its move tree and sends the whole annotated game;
  the server parses it and stores it only if the starting position and the main line's moves
  are exactly the stored ones, keeping its own headers. Imported annotations, clock comments
  (`[%clk …]`) included, stay as they are unless the user edits them.
- Whole-game saves, last one wins: one user edits their own game.

## Consequences

- One simple endpoint and one check, instead of an API per kind of annotation.
- The server rewrites the PGN text in python-chess's layout when it saves, so a game's text
  can look different after its first edit (same moves, same annotations).
- Editing the moves themselves, if ever wanted, needs its own decision: it means recomputing
  the fingerprint, positions and analysis.
