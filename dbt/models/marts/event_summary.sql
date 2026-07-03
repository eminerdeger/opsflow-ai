-- Per event type: volume, failure rate, latency and retry profile.
-- All time semantics come from event_timestamp (event time), never inserted_at.

select
    event_type,
    count(*) as event_count,
    count(*) filter (where is_failure) as failure_count,
    round(avg(case when is_failure then 1.0 else 0.0 end), 4) as failure_rate,
    round(avg(duration_ms), 1) as avg_duration_ms,
    round(avg(retry_count), 3) as avg_retry_count,
    min(event_timestamp) as first_event_at,
    max(event_timestamp) as last_event_at
from {{ ref('stg_events') }}
group by event_type
