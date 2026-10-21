"""Pure chess logic: PGN parsing, position hashing, move classification, tactics extraction.

Must not import Django (enforced by import-linter, see pyproject.toml). This code is tested
without a database and also runs in the bulk-import worker processes.
"""
