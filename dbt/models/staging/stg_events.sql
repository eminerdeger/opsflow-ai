-- Staging: rename/cast only. "timestamp" (event time) becomes event_timestamp;
-- inserted_at (load time) is kept separate so downstream models never mix the two.

select
    event_id,
    event_type,
    "timestamp" as event_timestamp,
    location_id,
    component_id,
    status,
    status in ('failed', 'timeout') as is_failure,
    duration_ms,
    confidence_score,
    retry_count,
    error_code,
    severity,
    correlation_id,
    metadata,
    inserted_at
from {{ source('opsflow_raw', 'raw_events') }}
