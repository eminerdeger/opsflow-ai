"""Shared defaults for the OpsFlow CLI and pipeline stages.

Everything here is a synthetic-project default; nothing references a real system.
"""

DEFAULT_SEED = 42
DEFAULT_EVENT_COUNT = 1000
DEFAULT_DURATION_MINUTES = 120

DEFAULT_EVENTS_PATH = "sample_data/events.jsonl"
DEFAULT_ANOMALIES_PATH = "sample_data/anomalies.json"
DEFAULT_REPORT_PATH = "reports/incident_report.md"
