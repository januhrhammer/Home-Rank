"""Reading settings from environment variables (config/env.py)."""

import datetime
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


@pytest.mark.parametrize(("value", "expected"), [("200", 200), ("0", 0)])
def test_integers(monkeypatch: pytest.MonkeyPatch, value: str, expected: int) -> None:
    monkeypatch.setenv("HR_TEST", value)

    assert env.integer("HR_TEST") == expected


def test_integer_default() -> None:
    default = 7

    assert env.integer("HR_TEST", default=default) == default


@pytest.mark.parametrize("value", ["200MB", "-1", "1.5", "two"])
def test_invalid_integer_is_an_error(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("HR_TEST", value)

    with pytest.raises(ImproperlyConfigured, match="a whole number"):
        env.integer("HR_TEST")


def test_database_urls_are_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HR_TEST", "postgres://homerank:secret@db:5432/homerank")

    database = env.database("HR_TEST")

    assert database["ENGINE"] == "django.db.backends.postgresql"
    assert (database["HOST"], database["NAME"]) == ("db", "homerank")


def test_choices_ignore_case_and_return_the_listed_spelling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HR_TEST", "warning")

    assert env.choice("HR_TEST", ["INFO", "WARNING"], default="INFO") == "WARNING"


def test_a_value_outside_the_choices_is_an_error_listing_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HR_TEST", "verbos")

    with pytest.raises(ImproperlyConfigured, match="INFO, WARNING"):
        env.choice("HR_TEST", ["INFO", "WARNING"], default="INFO")


def test_a_time_window_may_pass_midnight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HR_TEST", "23:30 - 7:00")

    assert env.time_window("HR_TEST") == (datetime.time(23, 30), datetime.time(7, 0))


def test_no_time_window_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HR_TEST", "")

    assert env.time_window("HR_TEST") is None


@pytest.mark.parametrize("value", ["night", "23:00", "25:00-07:00", "23:00-07:60", "8:00-8:00"])
def test_an_impossible_time_window_is_an_error(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("HR_TEST", value)

    with pytest.raises(env.InvalidValueError, match="HR_TEST must be"):
        env.time_window("HR_TEST")
