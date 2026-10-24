# 20. Repertoires hold named lines

Date: 2026-10-24

## Status

Proposed

## Context

A repertoire (ADR 0016) is one graph of moves for one colour. The maintainer builds them as one
line per repertoire, because a repertoire with many variations quickly becomes hard to follow,
but wants to drill several lines together. What they asked for: a repertoire such as "Ruy
Lopez" that holds one line per major variation ("Closed", "Open", "Berlin"), each edited and
drilled on its own or together with the others.

They chose (2026-10-24): existing repertoires become a repertoire with one line; two lines of a
repertoire may play different moves of the user's in the same position, with a warning; one
level only (repertoire, then lines; no folders inside folders).

Two ways to store lines were considered:

- **Each line its own moves**, as a repertoire today: simple to edit, but the moves the lines
  share (1.e4 e5 2.Nf3 Nc6 3.Bb5 in every Ruy Lopez line) are stored once per line, so they
  become one drill card per line, a drill of the whole repertoire asks the same move several
  times, and a transposition between two lines is two positions again, the problem ADR 0016
  avoided.
- **Lines as named sets of the repertoire's moves**: the repertoire keeps one graph of
  positions and moves, as now; a line is a name and the moves that belong to it, and a move
  shared by several lines belongs to each. One card per move, transpositions shared.

## Decision

- **Data**: `RepertoireMove` stays the repertoire's, unchanged (unique per repertoire, position
  and move). New `RepertoireLine` (repertoire, name unique within it, position for ordering) and
  a many-to-many between lines and moves. A move belongs to at least one line of its repertoire.
- **Editing** happens in a line: a move added there joins the repertoire's graph (or is found
  there already) and the line. Removing a move from a line takes it out of that line; the move
  itself, its card and the moves only reachable through it are deleted when no line has it any
  more (ADR 0016's rule, per line).
- **Conflicts**: a position where the repertoire has more than one move of the user's, coming
  from different lines, is listed as a conflict on the repertoire's page, with the lines. It is
  allowed, as alternatives are today.
- **Cards** stay one per move of the user's (ADR 0014/0016). Reviewing a move updates its one
  card, whichever drill asked for it.
- **Drills**: of the whole repertoire, as now; of one line or of several chosen lines, with the
  moves of those lines only. "Due" and "line" modes for both.
- **Bot games, gaps and explorer** use the whole repertoire, as now.
- **Import from PGN** goes into a line chosen by the user, or one line per game of the file,
  named after its `ChapterName` or `Event` header (as Lichess studies and course exports
  name chapters). Seeding from the user's games goes into a chosen line.
- **Migration**: each existing repertoire gets one line, "Main line", holding all its moves.
  Nothing else changes for existing data; cards keep their history.
- **API**: lines are a sub-resource, `/repertoires/{id}/lines` (list, create, rename, reorder,
  delete). Adding a move takes the line; a move's lines are part of its data. Drill endpoints
  take an optional list of line ids. The repertoire's own endpoints keep their shape.
- **Limits**: 100 lines per repertoire, in addition to ADR 0016's limits.

## Consequences

- The tree editor shows one line, with the repertoire's other lines' moves in the same
  positions marked as such; the repertoire page lists the lines and the conflicts.
- Deleting a line can delete moves (those in no other line) and their cards' history; the UI
  says how many before it does.
- Every move must stay in at least one line; the services keep it so, and tests check it.
- Supersedes ADR 0016's "repertoires are independent" only within a repertoire: two
  repertoires still share nothing.
