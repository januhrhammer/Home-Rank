# 16. Repertoires: moves keyed by position, drilled with FSRS

Date: 2026-10-23

## Status

Accepted

## Context

A repertoire is the set of opening moves a player has prepared for one colour: their own move
in each position they expect, and the opponent's replies they want to be ready for. Users build
one by hand on the board, import it from PGN (with variations), or start from what they
actually play in their games. They then want to see where their games left it ("gaps") and to
drill it with spaced repetition, like the puzzles (ADR 0014).

Openings transpose: 1. d4 Nf6 2. c4 e6 and 1. c4 e6 2. d4 Nf6 reach the same position. A tree
of nodes, each pointing to its parent, stores that position twice, with its own moves under
each copy; the two copies drift apart when the user edits one, and the same move becomes two
cards to drill.

## Decision

- **Data** (app `repertoire`): `Repertoire` (user, name unique per user, colour) and
  `RepertoireMove`, one row per move: the position it is played from (its Polyglot Zobrist hash
  and FEN), the move (UCI and SAN), the hash of the position it leads to, and a comment. A
  position has at most one row per move (unique repertoire, position, move). So the repertoire
  is a graph of positions, and a transposition is the same position, with the same moves,
  whichever way it was reached. The tree the user sees is drawn from the starting position by
  following the moves; a position reached a second time shows a "transposes to" link instead of
  its moves again.
- Every repertoire starts from the standard starting position.
- Several moves of the user's own in one position are allowed (a main move and alternatives).
- **Removing a move** also removes every move no longer reachable from the starting position.
- **Cards**: each of the user's own moves is one FSRS card (`ReviewCard` of type
  "repertoire", ADR 0014's model): the position and the move expected there. A transposition
  shares the card. The opponent's moves have no cards; drills play them automatically.
- **Seed from my games**: over the user's games with that colour from the starting position,
  up to a depth chosen by the user (default 12 plies): in positions where the user is to move,
  their most played move (ties: the one in more recent games); where the opponent is to move,
  every reply played in at least a chosen number of games (default 2). Seeding only adds moves
  that are missing; it never changes or removes what is there.
- **Gap report**, computed when asked for: each of the user's games with that colour is
  followed from the start while the position has moves in the repertoire. The first move that
  isn't one of them is a gap, either the user's ("you left your repertoire") or the opponent's
  ("not covered"). Gaps are grouped by position and move, with their games, most frequent first.
- **Drill**: "due" mode shows the repertoire's due cards one by one, each in its position after
  the opponent's last move; "line" mode plays a line from the start, the opponent's moves
  automatically, and asks for each of the user's moves. Each answer is a review: right on the
  first try is "Good", otherwise "Again" (the user is then shown the move). The user can change
  the rating, as with puzzles. Playing another of the repertoire's own moves in that position
  isn't wrong: the user is asked for the other one.
- **Limits**: 5,000 moves per repertoire, 50 repertoires per user, so that one user can't fill
  the disk and a whole repertoire can be sent to the browser at once.

## Consequences

- The tree is built in Python from all of a repertoire's moves, read in one query; with at most
  5,000 rows that is fast and keeps the database simple (no recursive queries).
- Two positions that differ only in the move counters are the same position (the Zobrist hash
  ignores them), as a player would see it.
- A user's move with several cards (the same position reached in two repertoires) is drilled
  once per repertoire; repertoires are independent.
- Repertoires don't share moves with each other or with the explorer; the explorer panel next to
  the editor shows the user's games and the reference databases for the position.
