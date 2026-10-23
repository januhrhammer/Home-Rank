# Development

How to set up Home-Rank on your machine and work on it.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) manages Python and the backend dependencies. It downloads the
  right Python version (3.12) by itself.
- [just](https://just.systems/) runs all project tasks.
- [Docker](https://docs.docker.com/engine/install/) with the Compose plugin runs the development
  database.
- [Node.js](https://nodejs.org/) 24, the version in `.nvmrc`, for the frontend. A version manager
  such as [fnm](https://github.com/Schniz/fnm) can switch to it automatically in this folder.
- pnpm, enabled once with `corepack enable pnpm`. `frontend/package.json` pins its version.
- curl, for downloading Stockfish (the chess engine) during setup. The download is a Linux
  program; on macOS, install Stockfish yourself (e.g. `brew install stockfish`) and set
  `STOCKFISH_PATH` in `.env` to where it is.

## First-time setup

```sh
just setup   # install dependencies, Stockfish and the git hooks
just check   # start the database and run every check
```

If `just check` passes, your setup works.

## Git hooks

Every `git commit` first runs quick checks (`.pre-commit-config.yaml`): file hygiene, a scan for
accidentally committed secrets (gitleaks), ruff, mypy and import-linter for the backend, and
Prettier, ESLint and tsc for the frontend. The commit message must
follow [Conventional Commits](https://www.conventionalcommits.org/), e.g.
`feat(import): resume interrupted imports`. Fix what they report instead of skipping them with
`--no-verify`; `just fmt` fixes formatting.

The first commit takes about a minute: pre-commit downloads Go once to build gitleaks. To run all
hooks on all files, e.g. after changing their configuration: `just pre-commit`.

## Everyday commands

Run `just` to list all tasks. The ones you need most:

| Command | What it does |
|---|---|
| `just dev` | Start the database, Django on <http://localhost:8100> and the frontend on <http://localhost:5173>. Ctrl+C stops both. |
| `just worker` | Run the background job worker, which also starts recurring jobs on schedule. PGN imports and Lichess/Chess.com syncs only run while it does; uploads wait in `data/` until then. Syncs make real requests to the two sites. |
| `just test` | Run all tests. Tests marked `engine` run Stockfish. |
| `just stockfish` | Download Stockfish to `.tools/stockfish/`, where the dev server and tests find it. `just setup` does this too. |
| `just fmt` | Format all code |
| `just gen-api` | Regenerate the frontend's API types after changing the backend API. `just check` fails while they are out of date. |
| `just build` | Build the Docker image as `home-rank:dev` (`docker/Dockerfile`) |
| `just e2e` | Test the whole app in a browser, running in Docker ([below](#end-to-end-tests)) |
| `just check` | Formatting, lint, types and tests. **Run it before every commit.** |

Most tasks also exist for one half of the project: `just test-backend -k settings` passes
arguments to pytest, `just test-frontend App` to Vitest, and there are `lint-backend`,
`fmt-frontend` and so on.

`just test-backend --cov` also reports which backend lines the tests don't reach.

Django uses port 8100 rather than its usual 8000, which other local projects often occupy. If
8100 is taken on your machine, change it in the `dev` recipe of the `justfile`.

## End-to-end tests

`just e2e` tests the whole app in a real browser (Chromium, driven by
[Playwright](https://playwright.dev)): it starts `compose.yaml` as a separate Compose project
(`home-rank-e2e`, on <http://localhost:8104>), with an empty database and an account of its own,
runs the tests in `frontend/e2e/`, and removes the containers and their data again. It builds the
Docker image first, so the first run takes a few minutes; later ones about a minute.

Before the first run, download Playwright's browser once: `pnpm exec playwright install chromium`
in `frontend/`. Arguments go to Playwright: `just e2e --headed` shows the browser,
`just e2e --debug` steps through a test. A failed test leaves a recording in
`frontend/test-results/`; `pnpm exec playwright show-trace <file>` replays it.

The end-to-end tests cover what the unit tests can't: the real server, the background worker and
files really uploaded by a browser. Keep them to the main journeys; details belong in the unit
tests.

## Continuous integration

GitHub Actions (`.github/workflows/`) runs on every pull request and every push to `main`:

- `ci.yml`: the same `just` recipes as `just check`, Django's deployment checks with the
  production settings, the file checks of the git hooks, a secret scan of new commits, and the
  Docker image built for amd64 and arm64 and scanned for known vulnerabilities. On pull
  requests also `just e2e`; when it fails, the run keeps Playwright's report and recordings as
  the artifact `e2e-results`.
- `pr-title.yml`: a pull request's title must be a Conventional Commit, because squash-merging
  turns it into the commit message on `main`.
- `codeql.yml`: GitHub's CodeQL security analysis of the Python and TypeScript code and of the
  workflows themselves, also weekly. Results appear under the repository's Security tab.

If `just check` passes locally, CI should too.

[Renovate](https://docs.renovatebot.com) proposes dependency updates every Monday
(`.github/renovate.json5`): patch updates of development tools in one pull request that merges
itself once CI passes, all other minor and patch updates in one pull request for review, and each
major update on its own. Security fixes come right away.

## Releases

Releases come from the commit messages on `main`, through
[release-please](https://github.com/googleapis/release-please) (`.github/workflows/release.yml`).
It keeps a release pull request open with the next version number and its `CHANGELOG.md` entry:
`feat` commits raise the minor version, `fix` the patch version, and while Home-Rank is 0.x
breaking changes raise the minor version too. Merging that pull request tags the version,
creates the GitHub release and publishes the Docker image for amd64 and arm64 as
`ghcr.io/januhrhammer/home-rank`, signed with cosign and with an SBOM attached.

## Settings and configuration

Django's settings live in `backend/config/settings/`:

| Module | Used by | Notes |
|---|---|---|
| `dev.py` | `manage.py`, `just dev` | Debug mode, fixed throwaway secret key, local database |
| `test.py` | pytest | Like dev, but without debug mode and development-only tools |
| `prod.py` | the Docker image | Requires `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL` and `HTTPS` |

Local development needs no configuration. To override something, copy `.env.example` to `.env` in
the repository root and uncomment what you need; the required values at its top are for Docker
Compose and can stay empty. `.env` is never committed.

To try the self-hosting setup locally, follow [self-hosting.md](self-hosting.md) with
`HOMERANK_PORT` set to a free port.

## Database

`just dev`, `just test` and `just migrate` start a PostgreSQL 18 container
(`docker/compose.dev.yaml`) and wait until it is ready. It listens on `localhost:5432` only, with
user, password and database all named `homerank`. Tests run in a separate `test_homerank` database
that is created and removed automatically.

- `just db-down` stops the container. Your data stays in the Docker volume `home-rank-dev_db-data`.
- To start over with an empty database:
  `docker compose -f docker/compose.dev.yaml down --volumes`.
- If port 5432 is already taken on your machine, change the port in `docker/compose.dev.yaml`
  and set a matching `DATABASE_URL` in `.env`.

## Trying the API

The API lives under <http://localhost:8100/api/v1/>, with interactive docs generated from the
code at <http://localhost:8100/api/v1/docs>. Create an account with
`just manage createsuperuser` first.

Most endpoints require login. On the docs page:

1. Run `POST /api/v1/auth/login` with your username and password.
2. **Reload the page.** Logging in issues a new CSRF token, which the page picks up only on
   reload; until then, state-changing requests fail with 403.

Other clients log in the way the frontend does:

1. `GET /api/v1/auth/csrf` sets the `csrftoken` cookie.
2. `POST /api/v1/auth/login` with `{"username": "...", "password": "..."}`, sending the cookie's
   value in an `X-CSRFToken` header. This sets the `sessionid` cookie and a new `csrftoken`.
3. Every further `POST`, `PUT`, `PATCH` or `DELETE` sends the current `csrftoken` value as
   `X-CSRFToken`.

After 10 failed logins from one IP address, logins from it are blocked for 15 minutes. To lift
a block early: `just manage axes_reset`.

Errors are JSON "problem details" (RFC 9457), for example
`{"type": "about:blank", "title": "Unauthorized", "status": 401, "detail": "Unauthorized"}`.
