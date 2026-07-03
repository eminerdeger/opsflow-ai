"""Idempotent Postgres ingestion for JSONL event streams (P1).

Design:
- events are validated through the same Pydantic schema as the rest of the platform
- schema is applied idempotently (CREATE TABLE IF NOT EXISTS from db/schema.sql)
- batch inserts use ON CONFLICT (event_id) DO NOTHING, so re-running ingestion is
  duplicate-safe and backfills never double-count
- the stored "timestamp" column is the true event time; inserted_at is load time
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

from opsflow.data_gen.schemas import OperationalEvent

INSERT_SQL = """
INSERT INTO raw_events (
    event_id, event_type, "timestamp", location_id, component_id, status,
    duration_ms, confidence_score, retry_count, error_code, severity,
    correlation_id, metadata
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (event_id) DO NOTHING
"""


@dataclass(frozen=True)
class IngestResult:
    rows_read: int
    rows_inserted: int
    rows_skipped: int


def load_schema_sql() -> str:
    return resources.files("opsflow.db").joinpath("schema.sql").read_text(
        encoding="utf-8"
    )


def event_to_row(event: OperationalEvent) -> tuple:
    """Map a validated event onto the raw_events column order of INSERT_SQL."""
    return (
        event.event_id,
        event.event_type.value,
        event.timestamp,
        event.location_id,
        event.component_id,
        event.status.value,
        event.duration_ms,
        event.confidence_score,
        event.retry_count,
        event.error_code,
        event.severity.value,
        event.correlation_id,
        json.dumps(event.metadata),
    )


def apply_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(load_schema_sql())
    conn.commit()


def ingest_events(
    conn, events: list[OperationalEvent], batch_size: int = 500
) -> IngestResult:
    """Batch-insert events; returns read/inserted/skipped counts.

    Inserted count is measured as the table-count delta so it stays correct
    regardless of driver rowcount semantics for executemany.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM raw_events")
        before = cur.fetchone()[0]
        for i in range(0, len(events), batch_size):
            batch = events[i : i + batch_size]
            cur.executemany(INSERT_SQL, [event_to_row(e) for e in batch])
        cur.execute("SELECT count(*) FROM raw_events")
        after = cur.fetchone()[0]
    conn.commit()
    inserted = after - before
    return IngestResult(
        rows_read=len(events),
        rows_inserted=inserted,
        rows_skipped=len(events) - inserted,
    )
