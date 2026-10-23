"""Reading settings from environment variables; used by the settings modules only.

Two rules that self-hosting with Docker needs:

- NAME_FILE=/path/to/file reads the value from that file (Docker secrets), every time it is
  asked for. Surrounding whitespace is removed, since secret files usually end with a newline.
- An empty value counts as unset, because Docker Compose passes an unset ${NAME} on as "".

A setting without a default is required: if it's missing, Django refuses to start.
"""

import os
import re
from datetime import time
from pathlib import Path
from typing import Any

import environ
from django.core.exceptions import ImproperlyConfigured

TRUE_WORDS = {"1", "true", "yes", "on"}
FALSE_WORDS = {"0", "false", "no", "off"}


class MissingVariableError(ImproperlyConfigured):
    def __init__(self, name: str) -> None:
        super().__init__(f"Set the {name} environment variable (or {name}_FILE)")


class ConflictingVariablesError(ImproperlyConfigured):
    def __init__(self, name: str) -> None:
        super().__init__(f"Set either {name} or {name}_FILE, not both")


class UnreadableFileError(ImproperlyConfigured):
    def __init__(self, name: str, path: str, reason: OSError) -> None:
        super().__init__(f"Can't read {name}_FILE ({path}): {reason.strerror}")


class InvalidValueError(ImproperlyConfigured):
    def __init__(self, name: str, value: str, expected: str) -> None:
        super().__init__(f"{name} must be {expected}, not {value!r}")


def _read(name: str) -> str | None:
    """The value of NAME, or of the file NAME_FILE points to; None if neither is set."""
    value = os.environ.get(name, "")
    path = os.environ.get(f"{name}_FILE", "")
    if value and path:
        raise ConflictingVariablesError(name)
    if path:
        try:
            value = Path(path).read_text(encoding="utf-8")
        except OSError as error:
            raise UnreadableFileError(name, path, error) from error
    return value.strip() or None


def string(name: str, default: str | None = None) -> str:
    value = _read(name)
    if value is not None:
        return value
    if default is not None:
        return default
    raise MissingVariableError(name)


def strings(name: str, default: list[str] | None = None) -> list[str]:
    """A comma-separated list, e.g. ALLOWED_HOSTS=chess.example.org,localhost."""
    value = _read(name)
    if value is not None:
        return [item.strip() for item in value.split(",") if item.strip()]
    if default is not None:
        return default
    raise MissingVariableError(name)


def boolean(name: str, default: bool | None = None) -> bool:
    value = _read(name)
    if value is None:
        if default is not None:
            return default
        raise MissingVariableError(name)
    if value.lower() in TRUE_WORDS:
        return True
    if value.lower() in FALSE_WORDS:
        return False
    raise InvalidValueError(name, value, "true or false")


def integer(name: str, default: int | None = None) -> int:
    """A whole number of zero or more, e.g. a size or a count."""
    value = _read(name)
    if value is None:
        if default is not None:
            return default
        raise MissingVariableError(name)
    if not value.isdigit():
        raise InvalidValueError(name, value, "a whole number")
    return int(value)


def choice(name: str, choices: list[str], default: str) -> str:
    """One of a few allowed values, in any case; returned as spelled in `choices`."""
    value = string(name, default)
    for allowed in choices:
        if value.lower() == allowed.lower():
            return allowed
    raise InvalidValueError(name, value, f"one of {', '.join(choices)}")


def time_window(name: str) -> tuple[time, time] | None:
    """A daily time window such as "23:00-07:00" (it may pass midnight); None if unset."""
    value = _read(name)
    if value is None:
        return None
    match = re.fullmatch(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", value)
    try:
        if match is None:
            raise ValueError  # noqa: TRY301 - handled right below, like an impossible time
        start = time(int(match[1]), int(match[2]))
        end = time(int(match[3]), int(match[4]))
    except ValueError:
        raise InvalidValueError(name, value, 'a time window such as "23:00-07:00"') from None
    if start == end:
        raise InvalidValueError(name, value, "a window with different start and end times")
    return start, end


def database(name: str, default: str | None = None) -> dict[str, Any]:
    """A database URL such as postgres://user:password@host:5432/name, as Django settings."""
    config: dict[str, Any] = environ.Env.db_url_config(string(name, default))
    return config
