-- Overall health per component across the loaded stream.

select
    component_id,
    count(*) as event_count,
    count(*) filter (where is_failure) as failure_count,
    round(avg(case when is_failure then 1.0 else 0.0 end), 4) as failure_rate,
    round(avg(duration_ms), 1) as avg_duration_ms,
    round(avg(retry_count), 3) as avg_retry_count,
    count(distinct location_id) as location_count,
    min(event_timestamp) as first_event_at,
    max(event_timestamp) as last_event_at
from {{ ref('stg_events') }}
group by component_id
