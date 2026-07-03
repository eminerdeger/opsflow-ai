# ADR 003 — Postgres + dbt as the minimal data platform layer

- **Status:** Accepted
- **Date:** 2026-07-03

## Context

P0 proves the incident loop on flat files. To demonstrate data-platform engineering
(warehousing, modeling, testing) the project needs a database layer — without
violating the no-over-engineering rule (no Kubernetes, Kafka, Terraform, Prometheus,
or managed cloud services).

## Decision

Use **PostgreSQL 16 in a single docker-compose container** as the store and
**dbt-core + dbt-postgres** as the modeling layer:

- `opsflow ingest` validates every row through the same Pydantic schema as P0 and
  batch-inserts into `raw_events` with `ON CONFLICT (event_id) DO NOTHING`, making
  ingestion idempotent (re-runs and backfills never double-count).
- Event time (`"timestamp"` → renamed to `event_timestamp` in staging) is kept
  strictly separate from load time (`inserted_at`); all models aggregate on event
  time so backfills cannot create false spikes.
- dbt stays minimal: 3 staging views (rename/cast only) and 3 table marts
  (`event_summary`, `ocr_health`, `component_health`) in schema `analytics`, with
  schema tests. `ocr_health` mirrors the Python detector's 5-minute event-time
  buckets so both layers describe anomalies identically.
- `psycopg` is an optional extra imported lazily, so P0 and the pytest suite never
  require a database.

## Consequences

- The full platform runs locally with `docker compose up -d` and two CLI commands;
  there is no cloud dependency and nothing to pay for.
- SQL-layer correctness is covered by dbt schema tests (17); live-database
  insert/idempotency behavior is verified by documented manual commands rather than
  pytest, keeping the test suite Docker-free.
- Postgres is not a columnar warehouse; at real scale the same dbt models would move
  to one. That is out of scope by design.
- dbt-core is pinned `>=1.10,<1.12` to avoid pre-release builds while staying
  compatible with dbt-postgres 1.10.x.
