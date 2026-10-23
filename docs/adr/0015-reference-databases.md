# 15. Reference databases: compact storage of millions of games

Date: 2026-10-23

## Status

Accepted

## Context

Reference databases such as Lumbra's GigaBase hold millions of games: over 12 million over the
board and over 6 million online games in 2026. Users browse them, search positions in them
("who else reached this?") and compare their own repertoire with them in an opening explorer.
Searches must answer in under half a second, and the data must fit on a homeserver's disk.

The first sketch stored one row per position per game: `(zobrist, game, ply, move)` with an
index on the hash. Measured with 1.5 million Lichess games (January 2015) and 30 plies per game,
that layout took 2.55 GB, mostly PostgreSQL's per-row overhead of about 24 bytes plus an index
entry for 13 bytes of data; for 12 million games about 20 GB, plus the games. Other tools avoid
per-position rows: ChessBase and Scid pack moves into a byte or two and search by scanning with
fast pre-filters (seconds), and Lichess's opening explorer keeps aggregates per position.

The same measurement showed how positions repeat: within the first 30 plies, 95 % of positions
occur in a single game, and positions seen in ten or more games are 0.5 % of them.

## Decision

- **Games** are stored with their headers as columns and their moves **packed into two bytes
  each** (from square, to square, promotion piece): about 200 bytes per game instead of the PGN
  text. The PGN is rebuilt from them when a game is shown or copied.
- **Explorer aggregates** are kept for positions seen in at least two games: per position and
  move, White's wins, draws, Black's wins, the sum of ratings and the last year played. A position
  seen in one game needs no aggregate: its one game says it all.
- **Position search** uses a packed index: entries of 13 bytes (hash, game, ply), sorted and
  stored in 131,072 buckets by the hash's top 17 bits (one row each, a few kB). A lookup reads one
  bucket and searches it. Positions seen in more than 10,000 games keep no game list: the
  explorer's counts cover them, and listing them would not help.
- Both are **rebuilt after each import** into a database, from a staging table of the import's
  positions. Adding a file later rebuilds them from the stored games.
- Positions are indexed up to **30 plies** per game by default; the depth is set per database.
- Each reference database's tables are **partitions** of shared tables, so deleting a database
  drops its partitions instead of deleting millions of rows.
- Reading: `.pgn`, `.pgn.gz`, `.pgn.bz2`, `.pgn.zst` and `.7z` (with `py7zr`, through a reader
  thread) are streamed and never unpacked to disk. An import notes the decompressed byte offset
  of each finished batch and resumes there, decompressing again up to it.

Measured with the 1.5 million games: aggregates 0.35 GB, packed index 0.51 GB, games 0.31 GB;
lookups in both layouts took 0.03 to 6 ms with warm caches. Parsing with python-chess ran at
about 890 games per second per process, and 8,100 per second with 15 processes including COPY.

## Consequences

- About a third of the space of the first sketch: for 12 million games roughly 7 to 9 GB plus
  about 3 GB of games, instead of about 20 GB plus games.
- Searching a bucket happens in Python, not in SQL; it is short and tested on its own.
- A reference database can't grow game by game; imports rebuild its indexes, which takes minutes
  for millions of games.
- 64-bit hashes can collide; a found game is checked by replaying its moves to the position.
