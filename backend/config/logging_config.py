"""Logging: every log entry, from our code or any library, is rendered by structlog.

Development shows readable, coloured lines; production writes one JSON object per line, which
log tools can parse. The settings modules choose via build_logging() (Django's LOGGING setting).
"""

from typing import Any

import structlog

# Added to every log entry, whether it comes from structlog or from plain `logging`, which
# Django and most libraries use.
SHARED_PROCESSORS: list[structlog.typing.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
]

# Our structlog loggers hand their entries to the standard `logging` module, so there is only
# one output path: the handler configured in build_logging().
structlog.configure(
    processors=[*SHARED_PROCESSORS, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


def make_formatter(*, json: bool) -> structlog.stdlib.ProcessorFormatter:
    renderers: list[structlog.typing.Processor]
    if json:
        renderers = [structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer()]
    else:
        renderers = [structlog.dev.ConsoleRenderer()]
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=SHARED_PROCESSORS,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, *renderers],
    )


def build_logging(*, json: bool, level: str = "INFO") -> dict[str, Any]:
    """Django's LOGGING setting: a single handler on the root logger, rendering via structlog."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"structlog": {"()": make_formatter, "json": json}},
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "structlog"}},
        "root": {"handlers": ["console"], "level": level},
        "loggers": {
            # Django gives these two loggers handlers of their own. Remove them and let the
            # entries propagate to ours, so each line appears once and in our format.
            "django": {"handlers": [], "level": level, "propagate": True},
            "django.server": {"handlers": [], "level": level, "propagate": True},
        },
    }
