"""Production settings must refuse to start without their required environment variables.

A self-hoster who forgets a variable should get a clear error at startup, not an instance
that runs with an insecure or broken fallback.
"""

import importlib
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest
from django.core.exceptions import ImproperlyConfigured

REQUIRED_VARIABLES = {
    "SECRET_KEY": "not-a-real-secret",
    "ALLOWED_HOSTS": "chess.example.org",
    "DATABASE_URL": "postgres://homerank:password@db:5432/homerank",
    "HTTPS": "true",
}
# Optional variables, cleared too, so that none leaks in from the environment running the tests.
OPTIONAL_VARIABLES = ["TRUST_PROXY_HEADERS", "CSRF_TRUSTED_ORIGINS", "LOG_FORMAT", "LOG_LEVEL"]


def import_prod_settings(monkeypatch: pytest.MonkeyPatch, variables: dict[str, str]) -> ModuleType:
    """Import config.settings.prod afresh, with exactly the given variables in the environment."""
    for name in [*REQUIRED_VARIABLES, *OPTIONAL_VARIABLES]:
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
    assert "chess.example.org" in settings.ALLOWED_HOSTS
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


def test_whitenoise_directly_follows_the_security_middleware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = import_prod_settings(monkeypatch, REQUIRED_VARIABLES)

    assert settings.MIDDLEWARE[:2] == [
        "django.middleware.security.SecurityMiddleware",
        "whitenoise.middleware.WhiteNoiseMiddleware",
    ]


@pytest.mark.parametrize(
    ("url", "cached_for_good"),
    [
        ("/assets/index-BxkfFJoz.js", True),  # Vite adds a hash
        ("/static/admin/css/base.3f2a1c9e8b7d.css", True),  # so does Django's manifest storage
        ("/index.html", False),
        ("/static/admin/css/base.css", False),
    ],
)
def test_only_files_with_a_hash_are_cached_for_good(
    monkeypatch: pytest.MonkeyPatch, url: str, *, cached_for_good: bool
) -> None:
    settings = import_prod_settings(monkeypatch, REQUIRED_VARIABLES)

    assert bool(re.match(settings.WHITENOISE_IMMUTABLE_FILE_TEST, url)) is cached_for_good


def test_https_secures_cookies_redirects_and_sets_hsts(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = import_prod_settings(monkeypatch, {**REQUIRED_VARIABLES, "HTTPS": "true"})

    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SECURE is True
    assert settings.SECURE_SSL_REDIRECT is True
    assert settings.SECURE_HSTS_SECONDS > 0


def test_plain_http_on_a_local_network(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = import_prod_settings(monkeypatch, {**REQUIRED_VARIABLES, "HTTPS": "false"})

    assert settings.SESSION_COOKIE_SECURE is False
    assert settings.SECURE_SSL_REDIRECT is False
    assert settings.SECURE_HSTS_SECONDS == 0


def test_proxy_headers_are_believed_only_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    default = import_prod_settings(monkeypatch, REQUIRED_VARIABLES)
    trusting = import_prod_settings(
        monkeypatch, {**REQUIRED_VARIABLES, "TRUST_PROXY_HEADERS": "true"}
    )

    assert getattr(default, "SECURE_PROXY_SSL_HEADER", None) is None
    assert trusting.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


def test_localhost_is_allowed_for_the_health_check(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = import_prod_settings(monkeypatch, REQUIRED_VARIABLES)

    assert settings.ALLOWED_HOSTS == ["chess.example.org", "localhost"]


def test_database_connection_attempts_time_out(monkeypatch: pytest.MonkeyPatch) -> None:
    default = import_prod_settings(monkeypatch, REQUIRED_VARIABLES)
    url = REQUIRED_VARIABLES["DATABASE_URL"] + "?connect_timeout=3"
    from_url = import_prod_settings(monkeypatch, {**REQUIRED_VARIABLES, "DATABASE_URL": url})

    assert default.DATABASES["default"]["OPTIONS"] == {"connect_timeout": 10}
    assert from_url.DATABASES["default"]["OPTIONS"] == {"connect_timeout": 3}


def test_logs_are_json_at_info_level_unless_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    default = import_prod_settings(monkeypatch, REQUIRED_VARIABLES)
    readable = import_prod_settings(
        monkeypatch, {**REQUIRED_VARIABLES, "LOG_FORMAT": "console", "LOG_LEVEL": "warning"}
    )

    assert default.LOGGING["formatters"]["structlog"]["json"] is True
    assert default.LOGGING["root"]["level"] == "INFO"
    assert readable.LOGGING["formatters"]["structlog"]["json"] is False
    assert readable.LOGGING["root"]["level"] == "WARNING"
