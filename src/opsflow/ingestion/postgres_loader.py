"""Postgres ingestion (P1 milestone — placeholder).

Design intent, implemented after P0 is stable:
- read events JSONL
- idempotent batch insert into raw events table (ON CONFLICT (event_id) DO NOTHING)
- watermark/state-based incremental loading on event time
"""
