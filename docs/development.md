# Development

How to set up Home-Rank on your machine and work on it.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) manages Python and the backend dependencies. It downloads the
  right Python version (3.12) by itself.
- [just](https://just.systems/) runs all project tasks.
- [Docker](https://docs.docker.com/engine/install/) with the Compose plugin runs the development
  database.

## First-time setup

```sh
just setup   # install the backend dependencies into backend/.venv
just check   # start the database and run every check
```

If `just check` passes, your setup works.

## Everyday commands

Run `just` to list all tasks. The ones you need most:

| Command | What it does |
|---|---|
| `just dev` | Start the database and Django's dev server on <http://localhost:8100> |
| `just test` | Run the tests; extra arguments go to pytest, e.g. `just test -k settings` |
| `just fmt` | Format all code |
| `just check` | Formatting, lint, types and tests. **Run it before every commit.** |

The dev server uses port 8100 rather than Django's usual 8000, which other local projects often
occupy. To use another port: `just dev 8200`.

## Settings and configuration

Django's settings live in `backend/config/settings/`:

| Module | Used by | Notes |
|---|---|---|
| `dev.py` | `manage.py`, `just dev` | Debug mode, fixed throwaway secret key, local database |
| `test.py` | pytest | Like dev, but without debug mode and development-only tools |
| `prod.py` | the Docker image | Requires `SECRET_KEY`, `ALLOWED_HOSTS` and `DATABASE_URL` |

Local development needs no configuration. To override something, copy `.env.example` to `.env` in
the repository root and uncomment what you need. `.env` is never committed.

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
