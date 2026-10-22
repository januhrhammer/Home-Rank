"""Reading settings from environment variables (config/env.py)."""

from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config import env


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HR_TEST", "HR_TEST_FILE"):
        monkeypatch.delenv(name, raising=False)


def test_reads_a_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HR_TEST", "value")

    assert env.string("HR_TEST") == "value"


def test_unset_variable_falls_back_to_the_default() -> None:
    assert env.string("HR_TEST", default="fallback") == "fallback"


def test_empty_variable_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Docker Compose passes an unset ${HR_TEST} through as an empty string.
    monkeypatch.setenv("HR_TEST", "")

    assert env.string("HR_TEST", default="fallback") == "fallback"


def test_missing_required_variable_is_an_error_naming_it() -> None:
    with pytest.raises(ImproperlyConfigured, match="HR_TEST"):
        env.string("HR_TEST")


def test_reads_the_value_from_a_file_without_its_trailing_newline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret = tmp_path / "secret"
    secret.write_text("s3cret\n")  # editors and `echo` end files with a newline
    monkeypatch.setenv("HR_TEST_FILE", str(secret))

    assert env.string("HR_TEST") == "s3cret"


def test_reads_the_file_again_on_every_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret = tmp_path / "secret"
    secret.write_text("first")
    monkeypatch.setenv("HR_TEST_FILE", str(secret))
    env.string("HR_TEST")

    secret.write_text("second")

    assert env.string("HR_TEST") == "second"


def test_value_and_file_together_are_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret = tmp_path / "secret"
    secret.write_text("from file")
    monkeypatch.setenv("HR_TEST", "direct")
    monkeypatch.setenv("HR_TEST_FILE", str(secret))

    with pytest.raises(ImproperlyConfigured, match="not both"):
        env.string("HR_TEST")


def test_unreadable_file_is_an_error_naming_the_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setenv("HR_TEST_FILE", str(missing))

    with pytest.raises(ImproperlyConfigured, match=str(missing)):
        env.string("HR_TEST")


def test_lists_are_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HR_TEST", " chess.example.org , localhost ,")

    assert env.strings("HR_TEST") == ["chess.example.org", "localhost"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", True), ("1", True), ("yes", True), ("false", False), ("0", False), ("no", False)],
)
def test_booleans(monkeypatch: pytest.MonkeyPatch, value: str, *, expected: bool) -> None:
    monkeypatch.setenv("HR_TEST", value)

    assert env.boolean("HR_TEST") is expected


def test_invalid_boolean_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HR_TEST", "maybe")

    with pytest.raises(ImproperlyConfigured, match="maybe"):
        env.boolean("HR_TEST")


def test_database_urls_are_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HR_TEST", "postgres://homerank:secret@db:5432/homerank")

    database = env.database("HR_TEST")

    assert database["ENGINE"] == "django.db.backends.postgresql"
    assert (database["HOST"], database["NAME"]) == ("db", "homerank")
