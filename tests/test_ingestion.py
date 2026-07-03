"""Unit tests for the Postgres ingestion layer that do NOT require Docker/Postgres.

Connection-dependent behavior (actual inserts, idempotent re-runs) is validated
manually against the docker-compose database; see PROGRESS.md.
"""

import json

from opsflow.db.connection import DbSettings
from opsflow.ingestion.postgres_loader import (
    INSERT_SQL,
    event_to_row,
    load_schema_sql,
)


def test_insert_sql_is_idempotent():
    assert "ON CONFLICT (event_id) DO NOTHING" in INSERT_SQL
    # Column list and placeholder count must match.
    columns = INSERT_SQL.split("(", 1)[1].split(")", 1)[0].split(",")
    placeholders = INSERT_SQL.count("%s")
    assert len(columns) == placeholders == 13


def test_schema_sql_defines_raw_events_idempotently():
    sql = load_schema_sql()
    assert "CREATE TABLE IF NOT EXISTS raw_events" in sql
    assert "event_id" in sql and "PRIMARY KEY" in sql
    assert '"timestamp"' in sql and "inserted_at" in sql


def test_event_to_row_maps_all_columns(spike_events):
    event = spike_events[0]
    row = event_to_row(event)
    assert len(row) == 13
    assert row[0] == event.event_id
    assert row[1] == event.event_type.value  # plain string, not enum
    assert row[2] == event.timestamp
    assert row[5] == event.status.value
    assert json.loads(row[12]) == event.metadata


def test_event_to_row_handles_optional_fields(baseline_events):
    # Non-OCR success events have no confidence score or error code.
    event = next(
        e
        for e in baseline_events
        if e.confidence_score is None and e.error_code is None
    )
    row = event_to_row(event)
    assert row[7] is None and row[9] is None


def test_db_settings_defaults_are_synthetic_local_values():
    settings = DbSettings()
    assert settings.host == "localhost"
    assert settings.password == "opsflow_local_dev"
    assert "host=localhost" in settings.conninfo()
