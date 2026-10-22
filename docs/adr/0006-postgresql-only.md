# 6. PostgreSQL only, no SQLite

Date: 2026-10-22

## Status

Accepted

## Context

Some self-hosted apps also run on SQLite, so that a small installation needs no database server.
Home-Rank targets homeservers, including Raspberry Pi-class machines, so the question came up
whether to support SQLite for very light installs.

Home-Rank already relies on PostgreSQL beyond what Django's ORM abstracts away:

- the job queue, Procrastinate ([ADR 0004](0004-job-queue.md)), stores jobs in PostgreSQL and
  uses `LISTEN/NOTIFY` and `SELECT ... FOR UPDATE SKIP LOCKED`;
- the container start takes a PostgreSQL advisory lock so that two containers never run
  migrations at once;
- reference-database imports load millions of games with `COPY` into tables partitioned per
  database, and the position index needs 64-bit integers and large indexes;
- planned data uses `jsonb` and array columns.

## Decision

Home-Rank supports **PostgreSQL only** (version 18, as shipped in `compose.yaml`; 16 or newer for
your own server). There is no SQLite mode, and tests run against PostgreSQL too.

## Consequences

- Every installation runs a PostgreSQL container. It needs about 40 MB of memory when idle,
  which fits even small machines.
- We can use PostgreSQL's features where they help, without fallbacks or a second code path to
  test.
- Backups are one `pg_dump` (see `docs/self-hosting.md`), and they include the job queue.
- Supporting another database later would mean replacing the job queue and the bulk-import
  code, so this decision is hard to reverse, deliberately.
