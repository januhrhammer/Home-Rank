#!/bin/sh
# Starts a Home-Rank container as the website ("web", the default) or the background job
# worker ("worker"). Anything else is run as a command, e.g.
#   docker compose run --rm web python manage.py createsuperuser
set -eu

case "${1:-web}" in
    web)
        # Bring the database schema up to date first, one container at a time. Set
        # MIGRATE_ON_START=false to apply migrations by hand instead.
        if [ "${MIGRATE_ON_START:-true}" != "false" ]; then
            python manage.py migrate_with_lock
        fi
        # Each gunicorn worker process handles one request at a time. That also limits how
        # many password checks (100 MiB of memory each) run at once, so keep WEB_WORKERS small
        # on small machines.
        exec gunicorn config.wsgi --bind 0.0.0.0:8000 --workers "${WEB_WORKERS:-2}"
        ;;
    worker)
        # Jobs run side by side: the analyses (at most ANALYSIS_CONCURRENCY at once), a novelty
        # search (one at a time, for hours), and two more, so imports and syncs needn't wait.
        exec python manage.py procrastinate worker --concurrency "$((${ANALYSIS_CONCURRENCY:-1} + 3))"
        ;;
    *)
        exec "$@"
        ;;
esac
