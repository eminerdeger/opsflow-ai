# SQL doctor

Review the SQL and dbt layer of this repo: $ARGUMENTS (default: src/opsflow/db/ and dbt/)

Check for:
1. **Idempotency**: inserts must be duplicate-safe (`ON CONFLICT DO NOTHING` on the
   natural key); re-running ingestion must never double-count.
2. **Event-time correctness**: all time-based models/metrics must use
   `event_timestamp`, never `ingested_at`, so backfills don't create false spikes.
3. **Index sanity**: indexes match the query patterns (time-range scans,
   component+time filters).
4. **dbt hygiene**: staging models only rename/cast, marts hold logic; every model
   has schema tests (unique/not_null on keys, accepted_values on enums).
5. **Synthetic-only rule**: no real table names, hosts, or credentials.

Report issues with file:line references and propose minimal fixes.
