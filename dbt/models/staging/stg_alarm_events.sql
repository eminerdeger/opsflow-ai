select *
from {{ ref('stg_events') }}
where event_type = 'system_alarm'
