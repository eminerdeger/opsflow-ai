# Assumptions & Decisions

Running log of synthetic-design assumptions, scenario assumptions, architecture
decisions, and fallback choices. Updated as the project evolves.

## Synthetic design assumptions

- **Domain vocabulary** is generic airport/logistics-style telemetry (baggage_scan,
  ocr_read, routing_decision, system_alarm, processing_delay, retry_event) with
  synthetic IDs (`LOC_A01…A04`, `OCR_GATE_01/02`, `ROUTER_01/02`, `SORTER_01/02`,
  `CONTROLLER_01`). None correspond to any real system.
- **Normal traffic**: ~3% background failure rate, OCR confidence ~N(0.93, 0.04),
  event mix weighted toward scans/OCR reads. Values chosen to look plausible, not
  calibrated to any real system.
- **Timestamps**: events are uniformly distributed over the generation timespan
  (default 2h ending "now"); tests pin `--start-time` for reproducibility. Timezone
  is always UTC.
- **Determinism**: one `random.Random(seed)` drives everything; same inputs → byte
  identical JSONL. Event IDs embed the sequence index to guarantee uniqueness.
- **Ground truth**: injected anomalous events carry `metadata.injected_anomaly=true`
  as a test oracle. The detector and RCA never read this flag.
- **Correlation IDs** simulate multi-event journeys via a small reuse pool (~30%
  reuse) rather than modeling full journey state machines — enough for blast-radius
  estimation without overbuilding.

## Scenario assumptions (ocr_failure_spike)

- Anomaly window covers fractions 0.55–0.80 of the timespan (~30 min of a 2h run).
- Inside the window, ~55% of events are converted to anomalous OCR reads on
  OCR_GATE_02 / LOC_A02 with 85% failure rate, confidence ~N(0.34, 0.09), 2–5
  retries, and error codes ERR_OCR_LOW_CONFIDENCE (70%) / ERR_OCR_TIMEOUT (30%).
- This models a localized optical/component fault: one component, one location,
  dominant error code, confidence/retry anti-correlation.

## Architecture decisions

- **Detector uses median/MAD robust z-score** over 5-minute event-time buckets
  instead of mean/std: the anomaly itself contaminates the baseline, and robust
  statistics keep the threshold meaningful without needing a labeled clean baseline.
  Guards: absolute failure-rate floor (0.15), minimum delta vs median (0.10),
  minimum bucket size (10 events), MAD scale floor (0.02) to avoid zero-variance
  blowups.
- **Consecutive flagged buckets merge** into one anomaly window; baseline metrics
  come from all non-flagged buckets of the same stream.
- **RCA is deterministic by design** (see CLAUDE.md rule 7): fixed tool pipeline,
  rule-based hypothesis with an evidence score (0–7) mapped to low/medium/high
  confidence. The tool trace is printed in the report.
- **CLI**: click with `python -m opsflow` entry; JSONL for events (stream-friendly,
  line-per-record), JSON for anomalies (small, structured), Markdown for reports.
- **src layout + editable install** rather than PYTHONPATH hacks.
- **P1 placeholders committed early** (db/schema.sql, docker-compose.yml, dbt dirs)
  to fix the target shape, but no P1 logic until P0 is stable — per priority rules.

## P1 decisions (Postgres + dbt)

- **Column naming**: raw_events stores the event time as `"timestamp"` (quoted,
  Postgres non-reserved keyword) and the load time as `inserted_at`. The staging
  model immediately renames `"timestamp"` → `event_timestamp` so downstream SQL
  never touches the quoted name; all time-based models use event time only.
- **Idempotency via count delta**: inserted-row counts are measured as the
  table-count difference before/after the batch loop rather than trusting
  executemany rowcount semantics — simple and driver-agnostic.
- **psycopg is optional**: imported lazily inside `opsflow ingest` and
  `db/connection.py`, so the P0 flow and its tests never require the `postgres`
  extra or a database.
- **dbt kept minimal**: 3 staging views + 3 table marts in schema `analytics`;
  staging only renames/casts (plus an `is_failure` convenience flag), marts hold
  aggregation logic. `ocr_health` uses the same 5-minute event-time buckets as the
  Python detector so both layers describe anomalies identically.
- **dbt profile handling**: `dbt/profiles.yml` is gitignored; it is a straight copy
  of the committed, fully synthetic `profiles.yml.example` (`dbt run --profiles-dir .`).
- **DB integration tests are manual**: pytest stays Docker-free (unit tests cover
  SQL shape, row mapping, schema file); insert/idempotency behavior is validated
  with documented manual commands in PROGRESS.md.

## Fallback choices

- If Postgres/dbt (P1) blocks, the P0 file-based flow is the shippable MVP.
- Generated `sample_data/*.jsonl|json` and `reports/incident_report.md` are
  gitignored (regenerable); one curated `reports/sample_incident_report.md` is
  committed as example output.
