# 22. Novelty search: tries that are hard for a given opponent to refute

Date: 2026-10-25

## Status

Proposed

## Context

The maintainer prepares for known opponents in weekend tournaments (opponents rated up to
2000): they know their colour and, from ChessBase, roughly what the opponent plays. They want
"practical tries": moves after the end of the expected line that give up some evaluation on
purpose, but whose refutation is hard to find for a player of that rating, ideally needing
several hard moves in a row. They enter the line by hand, and search between rounds (up to about
an hour) or overnight (up to about eight hours).

A spike (`.tools/novelty-spike`, results in `docs/progress.md`, "M10 (proposed)") tried this as
an expectimax search against a human model:

- The user's moves: Stockfish's best moves (MultiPV) whose evaluation stays within a risk
  budget, e.g. at most −1.5 pawns; the value of a position is the best of them.
- The opponent's moves: Maia-3 at the opponent's rating (ADR 0017), the moves covering 90 % of
  its probability, at most 3; the value is their probability-weighted mean.
- Leaves: Stockfish's evaluation as a winning chance (Lichess's formula).
- A try is a non-best move that scores higher against the model than the engine's best move.
  Finalists are checked again at depth 24 (the depth-14 evaluation was too optimistic, e.g. −1.05
  that was −1.51). The refutation's difficulty: along the engine's refutation, the probability
  that the model plays a move within 5 % winning chance of the best one.

It found known ideas from shallow starts (the McDonnell Gambit) and new ones from deep ones
(10.b4 in a deep Smith-Morra line, 65 % against 56 % for the engine's move; 11.Bb3 a6 12.Be3 63 %
against 49 %). On the maintainer's server (i5-9500T, 6 cores) three own moves deep took 526 s
for one line, four about 71 minutes; running the many short Stockfish searches on one engine per
core instead of one engine with all cores was 4.4 times faster (expected about 3 times in the
real search, which can't run everything side by side).

## Decision

- **Starting a search**: from any board position in the app (the analysis board, the repertoire
  editor, the game viewer), "Find tries from here", with the side to prepare for, the
  opponent's rating (the rating Maia plays at, see Open question), the risk budget (default 1.5
  pawns) and a time limit: "between rounds" (1 hour) or "overnight" (8 hours), or a custom one.
- **The search** runs as a background job in the worker, on its own queue, one at a time per
  server (it uses the whole processor). It deepens step by step: first two of the user's moves,
  then three, then four, then wider candidate lists at the first moves; after each step it
  stores the tries found so far, so results are there early and only get better. It stops at
  the time limit or when cancelled, keeping what it found.
- **Engines**: one single-threaded Stockfish per core the search may use
  (`NOVELTY_ENGINES`, default: all cores but one), sharing the work of each step; Maia runs in
  the job's process (milliseconds per position).
- **Stored per search**: the start (FEN and the moves leading there), side, opponent rating,
  budget, limit, status and progress; per try: the moves from the start to it, its evaluation at
  depth 24, its practical score and the engine move's, how often the line reaches it, and the
  refutation with the probability of each of the opponent's moves on it. Searches belong to their
  user like everything else.
- **Shown**: a "Novelty search" page lists the searches; a search's page lists its tries, best
  first (gain in practical score, weighted by how often the line reaches the try), each on a
  board with its refutation and the hard moves on it marked, and whether the position after the
  try occurs in a reference database (the first one, or one chosen). From a try: add it to a
  repertoire (as a new line, ADR 0020), or play it out against Maia at that rating.
- The search code (expectimax, the opponent model, scoring) lives in `engine`, without Django;
  the app stores and shows.

## Open question

Maia's ratings are Lichess ratings; the maintainer's opponents have national or FIDE ratings,
which are lower than Lichess ratings at club level. Proposed: the form asks for the opponent's
rating as the maintainer knows it plus its kind (Lichess, FIDE, national) and converts with a
rough published table, showing the Lichess rating it uses, which can be changed.

## Consequences

- A search occupies the server's processor for up to its limit; the number of engines is the
  way to keep the server responsive (and its fan quieter).
- Results depend on Maia's picture of a player of that rating; a prepared opponent who knows the
  line better than the model plays differently in theory, which is why searches start where the
  opponent's knowledge is expected to end.
- Tries are suggestions to check, not analysis to trust: each comes with its evaluation at depth
  24 and the refutation, to look at with the live analysis before playing it.
