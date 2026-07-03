-- OCR read quality per component per 5-minute event-time bucket.
-- Mirrors the detector's bucketing so dashboard curves match anomaly windows.

select
    component_id,
    location_id,
    to_timestamp(floor(extract(epoch from event_timestamp) / 300) * 300) as bucket_start,
    count(*) as read_count,
    count(*) filter (where is_failure) as failure_count,
    round(avg(case when is_failure then 1.0 else 0.0 end), 4) as failure_rate,
    round(avg(confidence_score)::numeric, 4) as avg_confidence,
    round(avg(retry_count), 3) as avg_retry_count
from {{ ref('stg_ocr_events') }}
group by component_id, location_id, bucket_start
