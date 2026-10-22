"""Reading settings from environment variables; used by the settings modules only.

Two rules that self-hosting with Docker needs:

- NAME_FILE=/path/to/file reads the value from that file (Docker secrets), every time it is
  asked for. Surrounding whitespace is removed, since secret files usually end with a newline.
- An empty value counts as unset, because Docker Compose passes an unset ${NAME} on as "".

A setting without a default is required: if it's missing, Django refuses to start.
"""

import os
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


def database(name: str, default: str | None = None) -> dict[str, Any]:
    """A database URL such as postgres://user:password@host:5432/name, as Django settings."""
    config: dict[str, Any] = environ.Env.db_url_config(string(name, default))
    return config
