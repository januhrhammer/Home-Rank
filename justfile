# Home-Rank development tasks. Run `just` to list them.
#
# Most tasks exist for both halves of the project: `just lint` runs `lint-backend` and
# `lint-frontend`, and each half can also be run on its own.

# Make recipe arguments available as "$@", so quoted arguments stay intact.
set positional-arguments

compose_dev := "docker compose -f docker/compose.dev.yaml"

# List all recipes
default:
    @just --list --unsorted

# Install all dependencies and the git hooks
setup: setup-backend setup-frontend

# Start the database, Django (http://localhost:8100) and Vite (http://localhost:5173)
dev: db-up
    #!/usr/bin/env bash
    # Both servers run side by side. Ctrl+C, or either one stopping, stops both: each gets a
    # single SIGTERM and shuts down its own child processes (uv passes it on to Django).
    # Signalling every process at once can leave Django's auto-reloader hanging. Vite runs
    # directly rather than via `pnpm dev`, because pnpm doesn't pass SIGTERM on to it.
    trap 'exit' INT TERM
    trap 'kill $backend $frontend 2>/dev/null' EXIT
    (cd backend && exec uv run python manage.py runserver 8100) &
    backend=$!
    (cd frontend && exec node_modules/.bin/vite) &
    frontend=$!
    wait -n

# Everything CI checks: formatting, lint, types, tests. Run before every commit.
check: fmt-check lint test

# Format all code
fmt: fmt-backend fmt-frontend

# Check formatting without changing any files
fmt-check: fmt-check-backend fmt-check-frontend

# Lint and type-check everything, and check that the frontend's API types are up to date
lint: lint-backend lint-frontend check-api

# Run all tests
test: test-backend test-frontend

# Regenerate the frontend's API types; run this after changing the backend API
gen-api: (_api-types justfile_directory() / "frontend/src/api/schema.d.ts")

# Fail if the frontend's API types don't match the backend (fix: just gen-api)
check-api:
    #!/usr/bin/env bash
    set -euo pipefail
    fresh=$(mktemp --suffix=.d.ts)
    trap 'rm -f "$fresh"' EXIT
    just _api-types "$fresh"
    cmp --silent "$fresh" frontend/src/api/schema.d.ts \
        || { echo "frontend/src/api/schema.d.ts is out of date: run just gen-api"; exit 1; }

# Write TypeScript types for the API, generated from Django's OpenAPI schema, to a file
_api-types output:
    #!/usr/bin/env bash
    set -euo pipefail
    schema=$(mktemp --suffix=.json)
    trap 'rm -f "$schema"' EXIT
    (cd backend && uv run python manage.py export_openapi_schema \
        --api config.api.api --sorted --output "$schema")
    (cd frontend && pnpm exec openapi-typescript "$schema" --output "{{ output }}")

# Build the Docker image as home-rank:dev
build:
    docker build --file docker/Dockerfile --tag home-rank:dev .

# Run the git commit checks on all files, not just the changed ones
pre-commit:
    uv run --project backend pre-commit run --all-files

# ---------------------------------------------------------------- backend (Django)

# Install the backend dependencies and the git hooks
[working-directory('backend')]
setup-backend: stockfish
    uv sync
    uv run pre-commit install

# Download Stockfish, the chess engine, into .tools/stockfish (for the dev server and tests)
stockfish:
    docker/get-stockfish.sh .tools/stockfish

# Format the backend code
[working-directory('backend')]
fmt-backend:
    uv run ruff format .

# Check the backend formatting
[working-directory('backend')]
fmt-check-backend:
    uv run ruff format --check .

# Lint and type-check the backend; also fail on a stale lockfile or a missing migration
[working-directory('backend')]
lint-backend:
    uv lock --check
    uv run ruff check .
    uv run mypy
    uv run lint-imports
    uv run python manage.py makemigrations --check --dry-run

# Run the backend tests; extra arguments go to pytest, e.g. `just test-backend -k settings`
[working-directory('backend')]
test-backend *args: db-up
    uv run pytest "$@"

# Run the background job worker; it also starts recurring jobs on schedule
[working-directory('backend')]
worker: db-up
    uv run python manage.py procrastinate worker --concurrency 3

# Apply migrations to the dev database
[working-directory('backend')]
migrate: db-up
    uv run python manage.py migrate

# Create a migration, e.g. `just migration games add_opening_index` (review it by hand!)
[working-directory('backend')]
migration app name:
    uv run python manage.py makemigrations {{ app }} --name {{ name }}
    uv run ruff format homerank/{{ app }}/migrations

# Run any manage.py command, e.g. `just manage shell`
[working-directory('backend')]
manage *args: db-up
    uv run python manage.py "$@"

# ---------------------------------------------------------------- frontend (React)

# Install the frontend dependencies
[working-directory('frontend')]
setup-frontend:
    pnpm install

# Format the frontend code
[working-directory('frontend')]
fmt-frontend:
    pnpm format

# Check the frontend formatting
[working-directory('frontend')]
fmt-check-frontend:
    pnpm format:check

# Lint and type-check the frontend
[working-directory('frontend')]
lint-frontend:
    pnpm lint
    pnpm typecheck

# Run the frontend tests; extra arguments go to Vitest, e.g. `just test-frontend App`
[working-directory('frontend')]
test-frontend *args:
    pnpm test "$@"

# ---------------------------------------------------------------- end-to-end tests

# Run the browser tests against a fresh Compose stack on port 8104; extra arguments go to
# Playwright, e.g. `just e2e --headed`. First run: `pnpm exec playwright install chromium` in
# frontend/
[working-directory('frontend')]
e2e *args:
    #!/usr/bin/env bash
    set -euo pipefail
    # compose.yaml, as self-hosters run it, but as its own project with its own containers and
    # volumes, so it never touches a local installation. Its settings come from a file of its
    # own instead of .env.
    env_file=$(mktemp)
    compose=(docker compose --file ../compose.yaml --project-name home-rank-e2e --env-file "$env_file")
    trap '"${compose[@]}" down --volumes --remove-orphans; rm -f "$env_file"' EXIT
    {
        echo "SECRET_KEY=$(openssl rand -hex 32)"
        echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
        echo "ALLOWED_HOSTS=localhost"
        echo "HTTPS=false"
        echo "HOMERANK_PORT=127.0.0.1:8104"
        # Shallow analyses: the tests check that Stockfish runs, not how well.
        echo "ANALYSIS_DEPTH=10"
    } > "$env_file"
    # Start from an empty database, even if an earlier run didn't get to clean up.
    "${compose[@]}" down --volumes --remove-orphans
    "${compose[@]}" up --detach --wait
    # The tests' account, with a new password each run.
    export E2E_USERNAME=e2e E2E_PASSWORD="$(openssl rand -hex 16)"
    "${compose[@]}" exec -T --env DJANGO_SUPERUSER_PASSWORD="$E2E_PASSWORD" web \
        python manage.py createsuperuser --noinput --username "$E2E_USERNAME" --email e2e@example.org
    pnpm e2e "$@"

# ---------------------------------------------------------------- database

# Start the dev database in the background and wait until it accepts connections
db-up:
    {{ compose_dev }} up --detach --wait

# Stop the dev database; its data stays in a Docker volume
db-down:
    {{ compose_dev }} down
