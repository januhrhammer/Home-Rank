# 4. Job queue: Procrastinate

Date: 2026-10-21

## Status

Accepted

## Context

Slow work must not run inside web requests, so a separate worker process handles it:

- PGN imports (minutes) and reference-database imports such as Lumbra's GigaBase (hours, and
  they must be able to resume after an interruption)
- syncing linked Lichess and Chess.com accounts every few hours
- engine analysis and tactics extraction, which are CPU-heavy; Stockfish runs as its own process

So there are few jobs, but some run for a long time. The UI shows a job's progress, and the
admin lists pending and failed jobs. Home-Rank is installed with a single Docker Compose file,
also on Raspberry Pi-class hardware, and already depends on PostgreSQL.

The usual choice for Django is Celery with Redis. The alternative considered is Procrastinate,
a job queue that stores jobs in PostgreSQL.

## Decision

Use **Procrastinate** with its Django integration.

- **No extra service.** Jobs are rows in the PostgreSQL database we already run; workers pick
  them up via `LISTEN/NOTIFY` and `SELECT ... FOR UPDATE SKIP LOCKED`. Celery needs a message
  broker (RabbitMQ or Redis) as another container to run, update and keep in memory, plus a
  separate `celery beat` process for periodic jobs.
- **Jobs are queued inside the database transaction.** Data and job are committed together, or
  neither is. With a Redis broker, a job can start before the transaction that created its data
  has been committed.
- **Long jobs are safe.** Procrastinate has no visibility timeout: a job stays "doing" as long as
  its worker is alive. With Celery and Redis, a job still running after the visibility timeout
  (one hour by default) is handed to another worker, so a multi-hour import would run twice
  unless that timeout is raised.
- **Job status is a table** that we can query, scope to the requesting user and show in the
  Django admin.
- Periodic jobs, retries, queues and locks are built in.

## Consequences

- One container fewer and less memory used; `pg_dump` backups include the queue.
- Throughput is far lower than with Redis-based queues. That doesn't matter at Home-Rank's scale
  of jobs per minute, not per millisecond.
- Procrastinate is a much smaller project than Celery, with a smaller community. To limit the
  risk, tasks stay thin wrappers that call services: replacing the queue would mean rewriting
  the `tasks.py` files and the job-status endpoint, not the business logic.
- It ties us further to PostgreSQL, which bulk imports (`COPY`) and partitioning do anyway.
- The worker runs synchronous tasks in threads, so CPU-heavy Python work would compete for the
  GIL. Heavy work therefore runs in separate processes: Stockfish as a subprocess, bulk-import
  parsing in a process pool.
