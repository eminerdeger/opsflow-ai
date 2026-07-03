"""Deterministic anomaly detection over synthetic event streams.

Approach: bucket the stream on event time, compute per-bucket failure rates, and
flag buckets whose rate is a robust-z outlier (median/MAD — robust to the anomaly
itself contaminating the baseline) above both an absolute floor and a minimum delta
vs the median. Consecutive flagged buckets are merged into one anomaly window, and
the remaining buckets form the baseline. No ML, no external services.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from opsflow.data_gen.schemas import OperationalEvent
from opsflow.detection.metrics import (
    WindowMetrics,
    bucket_events,
    compute_window_metrics,
    top_shares,
)


@dataclass(frozen=True)
class DetectorConfig:
    bucket_minutes: int = 5
    z_threshold: float = 4.0
    min_failure_rate: float = 0.15
    min_rate_delta: float = 0.10
    min_events_per_bucket: int = 10
    # Floor for the MAD-based scale estimate so near-zero variance can't explode z.
    mad_floor: float = 0.02


def detect_anomalies(
    events: list[OperationalEvent], config: DetectorConfig | None = None
) -> dict:
    config = config or DetectorConfig()
    buckets = bucket_events(events, config.bucket_minutes)
    bucket_size = timedelta(minutes=config.bucket_minutes)

    rates = []
    for _, bucket in buckets:
        failures = sum(1 for e in bucket if e.is_failure)
        rates.append(failures / len(bucket) if bucket else 0.0)

    med = median(rates) if rates else 0.0
    mad = median(abs(r - med) for r in rates) if rates else 0.0
    scale = max(1.4826 * mad, config.mad_floor)

    flagged: list[bool] = []
    robust_z: list[float] = []
    for (_, bucket), rate in zip(buckets, rates):
        z = (rate - med) / scale
        robust_z.append(z)
        flagged.append(
            len(bucket) >= config.min_events_per_bucket
            and rate >= config.min_failure_rate
            and (rate - med) >= config.min_rate_delta
            and z >= config.z_threshold
        )

    # Merge consecutive flagged buckets into anomaly windows.
    windows: list[tuple[int, int]] = []  # inclusive bucket index ranges
    start = None
    for i, is_flagged in enumerate(flagged):
        if is_flagged and start is None:
            start = i
        elif not is_flagged and start is not None:
            windows.append((start, i - 1))
            start = None
    if start is not None:
        windows.append((start, len(flagged) - 1))

    baseline_events = [
        e for (_, bucket), is_flagged in zip(buckets, flagged) if not is_flagged
        for e in bucket
    ]
    if baseline_events:
        baseline = compute_window_metrics(
            baseline_events,
            min(e.timestamp for e in baseline_events),
            max(e.timestamp for e in baseline_events),
        )
    else:
        now = datetime.now(timezone.utc)
        baseline = WindowMetrics(window_start=now, window_end=now)

    anomalies = []
    for n, (i, j) in enumerate(windows, start=1):
        window_start = buckets[i][0]
        window_end = buckets[j][0] + bucket_size
        window_events = [e for _, bucket in buckets[i : j + 1] for e in bucket]
        metrics = compute_window_metrics(window_events, window_start, window_end)
        peak_z = max(robust_z[i : j + 1])
        anomalies.append(
            {
                "anomaly_id": f"ANOM_{n:04d}",
                "type": "failure_rate_spike",
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "severity": _classify_severity(metrics.failure_rate),
                "peak_robust_z": round(peak_z, 2),
                "metrics": metrics.to_dict(),
                "baseline_metrics": baseline.to_dict(),
                "top_components": top_shares(metrics.failed_component_counts),
                "top_locations": top_shares(metrics.failed_location_counts),
                "top_error_codes": top_shares(metrics.error_code_counts),
            }
        )

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "detector_config": asdict(config),
        "bucket_count": len(buckets),
        "baseline_failure_rate_median": round(med, 4),
        "baseline": baseline.to_dict(),
        "anomalies": anomalies,
    }


def _classify_severity(failure_rate: float) -> str:
    if failure_rate >= 0.5:
        return "critical"
    if failure_rate >= 0.3:
        return "high"
    if failure_rate >= 0.15:
        return "medium"
    return "low"


def write_anomalies_json(result: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
