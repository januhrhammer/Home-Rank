# 9. Which side the user played

Date: 2026-10-22

## Status

Accepted

## Context

Many features need to know which side of a game was the user's: filtering by colour, and later
finding the user's own mistakes for puzzles and their repertoire gaps. Synced games know the
user's account name, but PGN files only contain player names, and a file may mix the user's
games with games between other players, such as a tournament or a master database.

Two ways were considered: asking at every upload which side the user played, or keeping a list
of the names the user plays under and comparing every game with it.

## Decision

- Each user has a list of **player names**, e.g. "Uhrhammer, Jan" and "januhrhammer". It is a
  field of the user model, `User.player_names`, rather than part of a separate settings table:
  it is a single list, read by every import.
- Every imported game is compared with the list, with names normalised so that spelling
  variants match ("Uhrhammer, Jan" and "uhrhammer,jan"). The result is stored per game as
  `Game.user_color`: white, black, or empty if the user didn't play, or played both sides.
- Changing the list updates `user_color` for all of the user's games.

Implemented in `homerank.chesslib.players`.

## Consequences

- Mixed files work: games of other players are stored with an empty `user_color`.
- Users have to enter their names once; until they do, no game has a side. The import page
  will point this out.
- Names written in a different order ("Jan Uhrhammer" and "Uhrhammer, Jan") don't match by
  themselves; users list both.
- Recomputing `user_color` after a change touches all of a user's games. It runs as a
  background job.
