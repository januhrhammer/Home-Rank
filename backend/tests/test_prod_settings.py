"""Production settings must refuse to start without their required environment variables.

A self-hoster who forgets a variable should get a clear error at startup, not an instance
that runs with an insecure or broken fallback.
"""

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest
from django.core.exceptions import ImproperlyConfigured

REQUIRED_VARIABLES = {
    "SECRET_KEY": "not-a-real-secret",
    "ALLOWED_HOSTS": "chess.example.org",
    "DATABASE_URL": "postgres://homerank:password@db:5432/homerank",
}


def import_prod_settings(monkeypatch: pytest.MonkeyPatch, variables: dict[str, str]) -> ModuleType:
    """Import config.settings.prod afresh, with exactly the given variables in the environment."""
    for name in REQUIRED_VARIABLES:
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(f"{name}_FILE", raising=False)
    for name, value in variables.items():
        monkeypatch.setenv(name, value)
    # Python runs a module's code only on its first import. Removing the cached module makes
    # the import below run prod.py again, against the environment set up above.
    monkeypatch.delitem(sys.modules, "config.settings.prod", raising=False)
    return importlib.import_module("config.settings.prod")


def test_reads_all_required_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = import_prod_settings(monkeypatch, REQUIRED_VARIABLES)

    assert settings.SECRET_KEY == "not-a-real-secret"
    assert settings.ALLOWED_HOSTS == ["chess.example.org"]
    assert settings.DATABASES["default"]["HOST"] == "db"


def test_debug_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = import_prod_settings(monkeypatch, REQUIRED_VARIABLES)

    assert settings.DEBUG is False


def test_logs_are_json(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = import_prod_settings(monkeypatch, REQUIRED_VARIABLES)

    assert settings.LOGGING["formatters"]["structlog"]["json"] is True


@pytest.mark.parametrize("missing", REQUIRED_VARIABLES)
def test_refuses_to_start_without(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    variables = {name: value for name, value in REQUIRED_VARIABLES.items() if name != missing}

    with pytest.raises(ImproperlyConfigured, match=missing):
        import_prod_settings(monkeypatch, variables)


def test_reads_the_secret_key_from_a_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Docker secrets: SECRET_KEY_FILE points to a file that holds the key.
    key_file = tmp_path / "secret_key"
    key_file.write_text("key-from-a-docker-secret\n")
    variables = {**REQUIRED_VARIABLES, "SECRET_KEY_FILE": str(key_file)}
    del variables["SECRET_KEY"]

    settings = import_prod_settings(monkeypatch, variables)

    assert settings.SECRET_KEY == "key-from-a-docker-secret"
