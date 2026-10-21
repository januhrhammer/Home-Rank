"""Health checks for containers: Docker's HEALTHCHECK and Compose's depends_on.

/healthz tells whether the process is alive, /readyz whether it can serve requests.
"""

from http import HTTPStatus

import structlog
from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_safe

logger = structlog.get_logger(__name__)


@require_safe
def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness: answers without touching anything else, so it fails only if the app is stuck."""
    return JsonResponse({"status": "ok"})


@require_safe
def readyz(request: HttpRequest) -> JsonResponse:
    """Readiness: the database is reachable."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        logger.exception("Readiness check failed: database unreachable")
        return JsonResponse({"status": "unavailable"}, status=HTTPStatus.SERVICE_UNAVAILABLE)
    return JsonResponse({"status": "ok"})
