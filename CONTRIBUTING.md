# Contributing to Home-Rank

Thanks for your interest! Home-Rank is in early development, so things still move quickly. Before
you work on something bigger than a small fix, please open an issue first, so we can agree on the
approach before you spend time on it.

Everyone taking part in the project follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting started

[docs/development.md](docs/development.md) explains the setup. In short:

```sh
just setup   # install dependencies and git hooks
just dev     # run everything locally
just check   # formatting, lint, types and tests: run before every commit
```

## How changes get in

- Work on a short-lived branch named after the change, e.g. `feat/pgn-import`,
  `fix/lichess-rate-limit` or `docs/self-hosting`, and open a pull request against `main`.
- Keep pull requests small enough to review in one sitting: ideally under 400 changed lines,
  not counting generated files and lockfiles.
- CI must pass. Pull requests are squash-merged, so the pull request's **title** becomes the
  commit message on `main`.

### Commit messages and pull request titles

Both follow [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`
in the imperative, lower case, without a trailing period, at most 72 characters. For example
`feat(import): resume interrupted imports`.

- Types: `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `revert`.
- Scopes name the area, for example `api`, `worker`, `db`, `import`, `sync`, `engine`, `ui`,
  `board`, `docker` or `deps`.
- A breaking change gets a `!` after the type or scope (`feat(api)!: …`) and a
  `BREAKING CHANGE:` footer that tells self-hosters what to do.
- One logical change per commit; formatting-only changes in their own commit.

The commit types decide the next version number and the changelog, so pick them with care: `feat`
and `fix` appear in the release notes.

## Code conventions

The tools enforce most of the style: Ruff and mypy (strict) for Python, ESLint, Prettier and
TypeScript (strict) for the frontend. Beyond that:

### Backend (Python, Django)

- Each Django app is layered. `api.py` parses input, calls a service or selector and returns a
  schema, with no logic and no database queries of its own. `services.py` changes state,
  `selectors.py` reads it, and `tasks.py` holds thin background jobs that call services, take ids
  rather than model instances, and are safe to run twice. Models hold fields and constraints,
  not workflows. No logic in signals.
- **Every query is scoped to the user it is for.** Each new resource that belongs to a user gets a
  test showing that one user can't see or change another's.
- `homerank.chesslib` and `homerank.engine` are plain Python and never import Django;
  import-linter checks this.
- Settings are read in `config/settings/` only, through `config/env.py`. Everywhere else uses
  `django.conf.settings`.
- Log with structlog, never `print`, and never log secrets, session tokens or whole PGNs.
- Model changes come with a migration that has a meaningful name, e.g.
  `just migration games add_opening_index`, and was read through by hand. A migration that is
  part of a release is never edited again: write a new one.

### Frontend (TypeScript, React)

- Function components and hooks; folders by feature.
- Data from the server goes through TanStack Query. The API types are generated from the backend
  with `just gen-api` and never written by hand; CI fails when they are out of date.
- Interface elements come from React Aria Components and are styled with CSS Modules and the
  design tokens in `frontend/src/styles/global.css`. They work with the keyboard and meet WCAG
  AA contrast.
- The chess board is wrapped once, in `frontend/src/components/Board/`; nothing else uses
  chessground directly.
- Text shown to users goes through the i18n helper in `frontend/src/lib/i18n.ts`.

### Tests

- New behaviour comes with tests, written along with the code. A bug fix starts with a test that
  fails without the fix.
- Tests run against a real PostgreSQL, never SQLite, and never call real external services: use
  recorded responses.
- Tests are deterministic: fixed seeds, frozen time, no dependence on their order.
- Keep test files small. Large PGN files never go into the repository.

### Dependencies, secrets and generated files

- New dependencies need a reason, given in the pull request. Prefer what the project already
  uses.
- No secrets, tokens or personal data in code, tests or fixtures. A git hook and CI scan for them.
- Generated files (API types, lockfiles) are regenerated, never edited by hand.

## Decisions

Decisions that are hard to reverse, such as the data model, the licence or the choice of a
library, are recorded as Architecture Decision Records in [docs/adr/](docs/adr/). If your change
makes such a decision, add one; [ADR 0001](docs/adr/0001-record-architecture-decisions.md) shows
the format.

## Licence

Home-Rank is licensed under the [AGPL-3.0-or-later](LICENSE). By contributing, you agree that
your contributions are licensed under the same terms.
