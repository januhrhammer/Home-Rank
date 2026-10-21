# 2. Licence: AGPL-3.0-or-later

Date: 2026-10-21

## Status

Accepted

## Context

Several core dependencies are licensed under the GPL:

| Dependency   | Licence          | How Home-Rank uses it                                |
|--------------|------------------|------------------------------------------------------|
| chessground  | GPL-3.0-or-later | board UI, bundled into the frontend                  |
| chessops     | GPL-3.0-or-later | chess rules and PGN, bundled into the frontend       |
| python-chess | GPL-3.0-or-later | PGN parsing, hashing, engine control in the backend  |
| Stockfish    | GPL-3.0-or-later | separate process, shipped in the Docker image        |

The first three become part of Home-Rank's own program, so Home-Rank as a whole must be released
under a GPL-compatible licence. A permissive licence (MIT, Apache-2.0) is not an option. The other
planned dependencies (Django, django-ninja, Procrastinate, React, psycopg, ...) are permissive or
LGPL and fit under either GPL variant.

That leaves GPL-3.0 or AGPL-3.0. The difference matters for a web app. The GPL only requires
sharing source code when copies are distributed, and running software as a website is not
distribution. The AGPL adds: whoever modifies the program and lets users interact with it over a
network must offer those users the modified source (AGPLv3 §13). Section 13 of each licence
explicitly allows combining GPLv3 and AGPLv3 code.

## Decision

Home-Rank is licensed under the **GNU Affero General Public License, version 3 or later**
(`AGPL-3.0-or-later`). The full text is in `LICENSE`.

## Consequences

- Self-hosters can run, modify and share Home-Rank freely. Running an instance creates no
  obligations as long as no one else uses a modified version of it.
- Anyone running a *modified* instance that other people use must offer them the modified source.
  To make that easy, the UI will show a link to the source code (added with the frontend shell).
- Published Docker images contain GPL binaries (Stockfish), so each image must point to the
  corresponding source of the bundled Stockfish version (release notes or image labels).
- Contributions are accepted under the same licence (inbound = outbound, no CLA). The project can
  never be relicensed under a permissive licence. "Or later" allows moving to a future AGPL
  version.
- Some companies forbid AGPL software internally. For a self-hosted tool aimed at individuals and
  clubs this is an acceptable trade-off.
