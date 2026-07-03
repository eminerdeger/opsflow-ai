"""Windowed metrics over event streams.

Everything is computed on event time (the `timestamp` field), never ingestion time,
so backfills and re-runs produce identical metrics.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable

from opsflow.data_gen.schemas import OperationalEvent


@dataclass
class WindowMetrics:
    window_start: datetime
    window_end: datetime
    event_count: int = 0
    failure_count: int = 0
    failure_rate: float = 0.0
    avg_confidence: float | None = None
    avg_retry_count: float = 0.0
    component_counts: dict[str, int] = field(default_factory=dict)
    location_counts: dict[str, int] = field(default_factory=dict)
    error_code_counts: dict[str, int] = field(default_factory=dict)
    failed_component_counts: dict[str, int] = field(default_factory=dict)
    failed_location_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "event_count": self.event_count,
            "failure_count": self.failure_count,
            "failure_rate": round(self.failure_rate, 4),
            "avg_confidence": (
                round(self.avg_confidence, 4) if self.avg_confidence is not None else None
            ),
            "avg_retry_count": round(self.avg_retry_count, 4),
        }


def compute_window_metrics(
    events: Iterable[OperationalEvent], window_start: datetime, window_end: datetime
) -> WindowMetrics:
    events = list(events)
    metrics = WindowMetrics(window_start=window_start, window_end=window_end)
    metrics.event_count = len(events)
    if not events:
        return metrics

    confidences = [e.confidence_score for e in events if e.confidence_score is not None]
    metrics.failure_count = sum(1 for e in events if e.is_failure)
    metrics.failure_rate = metrics.failure_count / len(events)
    metrics.avg_confidence = sum(confidences) / len(confidences) if confidences else None
    metrics.avg_retry_count = sum(e.retry_count for e in events) / len(events)
    metrics.component_counts = dict(Counter(e.component_id for e in events))
    metrics.location_counts = dict(Counter(e.location_id for e in events))
    metrics.error_code_counts = dict(
        Counter(e.error_code for e in events if e.error_code)
    )
    metrics.failed_component_counts = dict(
        Counter(e.component_id for e in events if e.is_failure)
    )
    metrics.failed_location_counts = dict(
        Counter(e.location_id for e in events if e.is_failure)
    )
    return metrics


def bucket_events(
    events: list[OperationalEvent], bucket_minutes: int
) -> list[tuple[datetime, list[OperationalEvent]]]:
    """Group events into fixed-size, epoch-aligned time buckets (sorted, gap-free)."""
    if not events:
        return []
    size = timedelta(minutes=bucket_minutes)
    timestamps = [e.timestamp for e in events]
    first, last = min(timestamps), max(timestamps)

    def bucket_start(ts: datetime) -> datetime:
        epoch = ts.timestamp()
        return datetime.fromtimestamp(
            epoch - epoch % size.total_seconds(), tz=ts.tzinfo
        )

    buckets: dict[datetime, list[OperationalEvent]] = {}
    cursor = bucket_start(first)
    while cursor <= last:
        buckets[cursor] = []
        cursor += size
    for event in events:
        buckets[bucket_start(event.timestamp)].append(event)
    return sorted(buckets.items())


def top_shares(counts: dict[str, int], limit: int = 3) -> list[dict]:
    """Rank a count dict as [{key, count, share}] with share of the total."""
    total = sum(counts.values())
    if total == 0:
        return []
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [
        {"key": key, "count": count, "share": round(count / total, 4)}
        for key, count in ranked
    ]
