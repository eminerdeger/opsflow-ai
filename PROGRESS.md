# Progress Log

## 2026-07-04 — P3-B: additional synthetic anomaly scenarios

### Completed milestones
- Two new config-driven scenarios in `scenarios.py`: `routing_latency_spike`
  (routing_decision duration ~8x profile + timeouts on ROUTER_02 / LOC_A03) and
  `alarm_storm` (critical system_alarm flood from CONTROLLER_01 / LOC_A01).
  `AnomalyScenario` gained defaulted generic fields (failed_status, failed_severity,
  duration_multiplier, optional confidence) so the generator stays scenario-agnostic;
  ocr_failure_spike behavior unchanged.
- Detector needed **no changes** — both scenarios surface as failure-rate spikes
  through the existing bucketed robust z-score.
- Deterministic RCA extended minimally: `avg_duration_ms` in window metrics, new
  `find_event_type_concentration` and `compare_event_type_duration` tools (duration
  compared within the dominant failing event type, since the whole-window average
  dilutes it), two new evidence scores (duration ratio, failed-event-type
  homogeneity; max score now 10), and two new rule-based hypothesis templates
  (`latency`, `alarm_storm`) with matching recommended actions. OCR template and
  actions intact.
- 6 new end-to-end tests (generation localization, detection, diagnosis failure
  mode/evidence for both scenarios); pytest now 27/27 passing.
- Smoke-tested all three scenarios via the CLI: each produces 1 detected window and
  a high-confidence, correctly-localized report (read_quality / latency /
  alarm_storm).
- Curated `reports/sample_incident_report.md` intentionally regenerated (report
  format gained duration row, event-type evidence, 10-point score); no generated
  sample_data files or local incident_report committed.

### Blockers
- None.

### Next steps
- P3 remaining (stretch, only if requested): Grafana dashboard.

## 2026-07-03 — P3-A: minimal GitHub Actions CI

- Added `.github/workflows/ci.yml`: on every push and pull request, ubuntu-latest,
  Python 3.12, `pip install -e ".[dev]"`, `pytest`. No Postgres/dbt in CI yet
  (deliberate — the suite is Docker-free by design).
- CI badge added at the top of README.md; project status updated.
- Local pytest: 21 passed.

## 2026-07-03 (evening) — P2 complete: portfolio polish

### Completed milestones
- Dependency stabilization: dbt extra now pins `dbt-core>=1.10,<1.12` (excludes the
  pre-release 1.12.0bX line that pip had resolved). Reinstalled → dbt-core 1.11.12
  stable + dbt-postgres 1.10.2; dbt run 6/6 and dbt test 17/17 re-verified against
  live Postgres.
- Fixed the dbt generic-test deprecation (MissingArgumentsPropertyInGenericTest…):
  `accepted_values` args moved under `arguments:` in staging schema.yml. dbt test now
  runs warning-free.
- README polish: example RCA output excerpt, tech stack, project status & roadmap,
  limitations sections added.
- docs/architecture.md: roadmap updated (P0/P1/P2 done), ADR index added.
- ADRs added under docs/adr/: 001 clean-room synthetic rebuild, 002 deterministic
  RCA instead of LLM agent, 003 Postgres + dbt as minimal platform layer.
- Repo audit: no generated/local files tracked; .gitignore covers sample_data,
  reports (except curated sample), dbt artifacts, profiles.yml, .env.
- Security audit: grepped for password/secret/token/api_key/credential/username/
  internal/prod/jdbc/oracle/mysql/mongodb/private-IP patterns/real vendor names
  (excluding .git/.venv/__pycache__/dbt target+logs). All hits are the rules docs
  themselves or the synthetic local-dev credential `opsflow_local_dev`. Clean.
- Curated sample report verified structurally identical to fresh P0 output
  (same sections, same high-confidence localization); kept as-is, no churn.

### Commands run (all verified working)
```
pytest                                                  # 21 passed
docker compose up -d                                    # postgres healthy
python -m opsflow generate-events --count 1000 --scenario ocr_failure_spike --output sample_data/events.jsonl
python -m opsflow ingest --input sample_data/events.jsonl   # 0 inserted, 1000 skipped (data from P1 run persists in volume — idempotent)
python -m opsflow ingest --input sample_data/events.jsonl   # 0 inserted, 1000 skipped
cd dbt && dbt run --profiles-dir . && dbt test --profiles-dir . && cd ..   # 6/6, 17/17
docker compose down
python -m opsflow detect-anomalies ... && python -m opsflow diagnose ...   # high-confidence report, OCR_GATE_02/LOC_A02
pytest                                                  # 21 passed
```

### Blockers
- None.

### Next steps
- P3 (stretch, only if requested): GitHub Actions CI, Grafana dashboard, more
  anomaly scenarios (routing storm, controller flap).

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
