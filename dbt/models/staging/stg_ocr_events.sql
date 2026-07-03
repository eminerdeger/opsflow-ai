select *
from {{ ref('stg_events') }}
where event_type = 'ocr_read'
