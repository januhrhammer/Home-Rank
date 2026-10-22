# syntax=docker/dockerfile:1
#
# One image for both the website and the background job worker (see docker/entrypoint.sh).
# Build from the repository root:  just build   (or: docker build -f docker/Dockerfile .)
#
# Three stages: the first two build things, and only the third becomes the image, without the
# build tools. Dependency files are copied before the code, so Docker's cache keeps installed
# dependencies when only the code changes.

# ---------------------------------------------------------------- 1: build the frontend
FROM node:24-slim AS frontend
WORKDIR /app/frontend
# pnpm comes through corepack, in the version package.json asks for.
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# ---------------------------------------------------------------- 2: backend dependencies
FROM python:3.12-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.9.22 /uv /usr/local/bin/uv
WORKDIR /app/backend
# Compile Python files ahead of time (the running container needn't write anything), copy
# packages instead of linking them to uv's cache, and use this image's Python.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./

# ---------------------------------------------------------------- 3: the image that runs
FROM python:3.12-slim
LABEL org.opencontainers.image.title="Home-Rank" \
      org.opencontainers.image.source="https://github.com/januhrhammer/Home-Rank" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"

# uv installed everything in stage 2, so the base image's pip is never used here: without it,
# its security advisories don't concern this image.
RUN python -m pip uninstall --yes --no-cache-dir pip \
 && useradd --system --create-home --uid 10001 homerank
WORKDIR /app/backend
COPY --from=backend /app/backend ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
COPY docker/entrypoint.sh /app/entrypoint.sh
ENV PATH="/app/backend/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Prepare static files now rather than at every start: compressed copies of the frontend, and
# the admin's files collected for WhiteNoise. The production settings refuse to load without
# their variables, so collectstatic gets placeholders that exist only for this one command.
RUN python -m whitenoise.compress /app/frontend/dist \
 && SECRET_KEY=build-only ALLOWED_HOSTS=localhost HTTPS=false \
    DATABASE_URL=postgres://build@localhost/build \
    python manage.py collectstatic --noinput

# The homerank user, by number: some platforms can only check numeric IDs for "not root".
USER 10001
EXPOSE 8000
# For the website. compose.yaml gives the worker container its own check.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=4)"]
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
