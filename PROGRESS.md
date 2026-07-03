# Progress Log

## 2026-07-03 (late) — P1 complete: Postgres ingestion + dbt layer

### Completed milestones
- `opsflow ingest`: validates JSONL through the existing Pydantic schema, applies
  db/schema.sql idempotently (CREATE IF NOT EXISTS), batch-inserts with
  ON CONFLICT (event_id) DO NOTHING, reports read/inserted/skipped counts,
  and gives an actionable error if the database is down
- `db/connection.py`: OPSFLOW_DB_* env settings (synthetic local defaults matching
  docker-compose.yml); psycopg imported lazily so P0 never needs it
- raw_events schema finalized: event_id PK, "timestamp" = event time,
  inserted_at = load time, metadata JSONB, time + component indexes
- dbt layer: sources.yml, staging (stg_events, stg_ocr_events, stg_alarm_events),
  marts (event_summary, ocr_health with 5-min buckets mirroring the detector,
  component_health), schema tests
- pyproject extras: `postgres` (psycopg) and `dbt` (dbt-postgres)

### Commands run (all verified working)
```
docker compose up -d                                   # postgres:16-alpine, healthy
python -m opsflow generate-events --count 1000 --scenario ocr_failure_spike --output sample_data/events.jsonl
python -m opsflow ingest --input sample_data/events.jsonl   # read=1000 inserted=1000 skipped=0
python -m opsflow ingest --input sample_data/events.jsonl   # read=1000 inserted=0 skipped=1000  ← idempotent
cd dbt && dbt run --profiles-dir . && dbt test --profiles-dir . && cd ..
pytest
```
- dbt run: 6 models OK (3 views, 3 tables in schema `analytics`)
- dbt test: 17/17 PASS (not_null/unique on event_id, accepted_values on
  event_type + status, mart key tests)
- Mart sanity check: `analytics.component_health` shows OCR_GATE_02 at 51.4%
  failure rate vs 3–5% for all other components — matches the injected scenario
- P0 re-verified after P1: detect-anomalies + diagnose still produce the correct
  high-confidence report

### Tests
- 21 passed, 0 failed (16 P0 + 5 new Docker-free ingestion unit tests)
- DB-dependent behavior (insert + idempotent re-run) is validated manually with the
  commands above rather than forced into pytest (would make the suite require Docker)

### Notes / minor observations
- pip resolved dbt-core to 1.12.0-b3 (beta) alongside dbt-postgres 1.10.2; both work.
  dbt prints a deprecation warning about generic-test argument style
  (MissingArgumentsPropertyInGenericTestDeprecation) — cosmetic, tests all pass.
- `dbt/profiles.yml` is generated locally from profiles.yml.example (gitignored).

### Blockers
- None.

### Next steps
- P2: coverage report, ADR(s), refresh sample report, README/docs final polish
- Optional P1 hardening: watermark-based incremental ingest state, retention config

## 2026-07-03 — Phase 1 + Phase 2 (P0) complete

### Completed milestones
- Repository scaffolding: pyproject.toml (src layout, click + pydantic, dev extras),
  .gitignore, .env.example, CLAUDE.md, README.md, ASSUMPTIONS.md, docs, .claude/commands
- Synthetic event model: Pydantic `OperationalEvent` + enums (6 event types, 4 statuses)
- Config-driven scenarios: `baseline`, `ocr_failure_spike` (scenarios.py registry)
- Deterministic seeded generator with anomaly-window injection and JSONL I/O
- Anomaly detector: event-time bucketing, median/MAD robust z-score, window merging,
  baseline metrics, severity classification, JSON output
- Deterministic RCA: 11 tool functions, DiagnosisAgent with tool trace, rule-based
  hypothesis (evidence score → confidence), Markdown report writer
- CLI: `generate-events`, `detect-anomalies`, `diagnose` (+ `ingest` P1 stub)
- P1 placeholders: docker-compose.yml (postgres:16), db/schema.sql, dbt project stubs

### Commands run (verified working)
```
python -m opsflow generate-events --count 1000 --scenario ocr_failure_spike --output sample_data/events.jsonl
python -m opsflow detect-anomalies --input sample_data/events.jsonl --output sample_data/anomalies.json
python -m opsflow diagnose --input sample_data/anomalies.json --events sample_data/events.jsonl --output reports/incident_report.md
pytest
```
Pipeline result: 1000 events → 1 anomaly window detected (failure rate 47.7% vs 2.7%
baseline) → high-confidence RCA report correctly localizing OCR_GATE_02 / LOC_A02 /
ERR_OCR_LOW_CONFIDENCE.

### Tests
- 16 passed, 0 failed (`pytest`, Python 3.13, ~0.1s)
- Coverage: generator count/schema/determinism/injection, detector true+false-positive
  behavior and config, RCA evidence/hypothesis/report sections, CLI end-to-end

### Blockers
- None.

### Next steps
- P1: Postgres ingestion (`opsflow ingest`, idempotent ON CONFLICT DO NOTHING,
  watermark-based), dbt staging/marts + tests against docker-compose Postgres
- P2: coverage report, docs/architecture.md polish, sample report refresh

### Assumptions
- See ASSUMPTIONS.md (kept current in the same commits).
