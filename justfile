# Home-Rank development tasks. Run `just` to list them.

# Make recipe arguments available as "$@", so quoted arguments stay intact.
set positional-arguments

compose_dev := "docker compose -f docker/compose.dev.yaml"

# List all recipes
default:
    @just --list --unsorted

# Install all dependencies
[working-directory('backend')]
setup:
    uv sync

# Start the dev database and Django's dev server on http://localhost:8100 (or another port)
[working-directory('backend')]
dev port="8100": db-up
    uv run python manage.py runserver {{ port }}

# Everything CI checks: formatting, lint, types, tests. Run before every commit.
check: fmt-check lint test

# Format all code
[working-directory('backend')]
fmt:
    uv run ruff format .

# Check formatting without changing any files
[working-directory('backend')]
fmt-check:
    uv run ruff format --check .

# Lint and type-check; also fail on a stale lockfile or a missing migration
[working-directory('backend')]
lint:
    uv lock --check
    uv run ruff check .
    uv run mypy
    uv run python manage.py makemigrations --check --dry-run

# Run the tests; extra arguments go to pytest, e.g. `just test -k settings`
[working-directory('backend')]
test *args: db-up
    uv run pytest "$@"

# Apply migrations to the dev database
[working-directory('backend')]
migrate: db-up
    uv run python manage.py migrate

# Create a migration, e.g. `just migration games add_opening_index` (review it by hand!)
[working-directory('backend')]
migration app name:
    uv run python manage.py makemigrations {{ app }} --name {{ name }}

# Run any manage.py command, e.g. `just manage shell`
[working-directory('backend')]
manage *args: db-up
    uv run python manage.py "$@"

# Start the dev database in the background and wait until it accepts connections
db-up:
    {{ compose_dev }} up --detach --wait

# Stop the dev database; its data stays in a Docker volume
db-down:
    {{ compose_dev }} down
