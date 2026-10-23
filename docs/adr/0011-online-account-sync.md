# 11. Syncing games from Lichess and Chess.com

Date: 2026-10-22

## Status

Accepted

## Context

Most players' games live on Lichess or Chess.com. Both publish a player's games without a
login: Lichess streams them from its game export API, Chess.com offers one archive per month.
Home-Rank should import them regularly, without the user downloading PGN files, and without
fetching everything again each time.

Both sites ask API users to be gentle: Lichess answers too many requests with HTTP 429 and
expects clients to wait a minute; Chess.com wants requests one at a time and a User-Agent that
says who is asking.

## Decision

- A user links accounts (`sync.LinkedAccount`: platform and username, unique per user whatever
  the case). Only public data is read; there is no login with the sites (OAuth) for now.
- Each sync is a background job with its own record (`sync.SyncRun`: status, counts of
  imported, duplicate and broken games, the first problems), like a file import.
- Synced games are ordinary games with `source` lichess or chesscom and the site's game id as
  `source_id`, deduplicated like file imports (ADR 0008). A game already imported from a PGN
  file is not stored twice.
- **Incremental**: each account keeps a cursor, `synced_until`, before which all games are
  stored.
  - Lichess: games are requested oldest first, from the time the newest stored game began;
    the cursor moves on after each batch, so an interrupted sync resumes where it stopped.
  - Chess.com: the list of monthly archives is fetched, then every month from the cursor's
    on. A month that ended before the sync started is complete; the cursor moves past it.
    The current month is fetched again by the next sync.
- Only standard chess is imported; Lichess is asked for standard games only, and Chess.com
  games with other rules (Chess960, Bughouse, …) are skipped.
- **Rate limits**: requests are made one at a time. On HTTP 429 the sync waits for the time
  the site names (Retry-After), at least 60 seconds, and tries again, up to three times.
- Requests carry the User-Agent `Home-Rank (+<source code URL>)`, plus a contact
  (an email address or URL) if the operator sets `SYNC_CONTACT`.
- **Schedule**: a periodic job queues a sync for every enabled account whose last sync is
  older than `SYNC_INTERVAL_HOURS` (default 6; 0 turns scheduled syncs off). Users can also
  sync an account at once. Syncs share the imports' lock per user, so two jobs never store the
  same user's games at the same time.
- **The user's side**: linking an account adds its username to the user's player names
  (ADR 0009), if it isn't there yet, and updates the side of all their games. The player names
  stay the one place that says who the user is; unlinking keeps the name.

## Consequences

- No network requests happen while a page waits: linking doesn't check that the account exists.
  The first sync reports "no such player" instead.
- A Lichess game that is still being played when its account is synced is missed if a later
  game is stored in the same sync, because the cursor passes its start. This mostly affects
  correspondence games; it can be fixed later by requesting a few days again each time.
- Without a login, Lichess sends about 20 games a second: a first sync of 10,000 games takes
  around eight minutes.
