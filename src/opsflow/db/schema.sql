-- OpsFlow AI raw events schema (P1).
-- Idempotent loading: event_id is the natural key; loader uses ON CONFLICT DO NOTHING.
-- "timestamp" is the true event time (event-time correctness); inserted_at is load time.

CREATE TABLE IF NOT EXISTS raw_events (
    event_id         TEXT PRIMARY KEY,
    event_type       TEXT NOT NULL,
    "timestamp"      TIMESTAMPTZ NOT NULL,
    location_id      TEXT NOT NULL,
    component_id     TEXT NOT NULL,
    status           TEXT NOT NULL,
    duration_ms      INTEGER NOT NULL,
    confidence_score DOUBLE PRECISION,
    retry_count      INTEGER NOT NULL DEFAULT 0,
    error_code       TEXT,
    severity         TEXT NOT NULL,
    correlation_id   TEXT NOT NULL,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    inserted_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_raw_events_timestamp ON raw_events ("timestamp");
CREATE INDEX IF NOT EXISTS idx_raw_events_component ON raw_events (component_id, "timestamp");
