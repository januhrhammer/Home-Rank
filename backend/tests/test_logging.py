"""Production logs: one JSON object per line, whether the entry comes from us or a library."""

import io
import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
import structlog

from config.logging_config import make_formatter

LOGGER_NAME = "homerank.test_logging"
DELETED_SESSIONS = 3


@pytest.fixture
def json_lines() -> Iterator[io.StringIO]:
    """Capture what the production formatter writes for LOGGER_NAME."""
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(make_formatter(json=True))
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(handler)
    logger.propagate = False  # keep these test entries out of the global handlers
    yield output
    logger.removeHandler(handler)
    logger.propagate = True


def only_entry(output: io.StringIO) -> Any:
    [line] = output.getvalue().splitlines()
    return json.loads(line)


def test_library_log_lines_become_json(json_lines: io.StringIO) -> None:
    logging.getLogger(LOGGER_NAME).warning("disk %s is full", "/data")

    entry = only_entry(json_lines)

    assert entry["event"] == "disk /data is full"
    assert entry["level"] == "warning"
    assert entry["logger"] == LOGGER_NAME
    assert entry["timestamp"].endswith("Z")  # UTC


def test_our_fields_become_json_fields(json_lines: io.StringIO) -> None:
    structlog.get_logger(LOGGER_NAME).info("Deleted expired sessions", count=DELETED_SESSIONS)

    entry = only_entry(json_lines)

    assert entry["event"] == "Deleted expired sessions"
    assert entry["count"] == DELETED_SESSIONS


def test_tracebacks_become_structured_data(json_lines: io.StringIO) -> None:
    try:
        int("not a number")
    except ValueError:
        structlog.get_logger(LOGGER_NAME).exception("Something failed")

    entry = only_entry(json_lines)

    assert entry["exception"][0]["exc_type"] == "ValueError"
