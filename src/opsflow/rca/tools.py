"""Deterministic RCA tool functions.

Each function is a pure "tool" over the event data: it inspects evidence and returns
structured results. The diagnosis agent orchestrates these tools; nothing here
invents explanations that are not backed by computed numbers.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from opsflow.data_gen.generator import read_events_jsonl
from opsflow.data_gen.schemas import OperationalEvent
from opsflow.detection.metrics import (
    bucket_events,
    compute_window_metrics,
    top_shares,
)


def load_events(path: Path) -> list[OperationalEvent]:
    return read_events_jsonl(path)


def filter_events_by_window(
    events: list[OperationalEvent], start: datetime, end: datetime
) -> list[OperationalEvent]:
    return [e for e in events if start <= e.timestamp < end]


def compare_baseline_vs_anomaly(
    events: list[OperationalEvent], window_start: datetime, window_end: datetime
) -> dict:
    """Compare the anomaly window against everything outside it (the baseline)."""
    window = filter_events_by_window(events, window_start, window_end)
    baseline = [e for e in events if not (window_start <= e.timestamp < window_end)]
    w = compute_window_metrics(window, window_start, window_end)
    if baseline:
        b = compute_window_metrics(
            baseline,
            min(e.timestamp for e in baseline),
            max(e.timestamp for e in baseline),
        )
    else:
        b = compute_window_metrics([], window_start, window_end)

    def _delta(window_val, baseline_val):
        if window_val is None or baseline_val is None:
            return None
        return round(window_val - baseline_val, 4)

    duration_ratio = None
    if w.avg_duration_ms is not None and b.avg_duration_ms:
        duration_ratio = round(w.avg_duration_ms / b.avg_duration_ms, 2)

    return {
        "baseline": b.to_dict(),
        "anomaly": w.to_dict(),
        "failure_rate_delta": _delta(w.failure_rate, b.failure_rate),
        "avg_confidence_delta": _delta(w.avg_confidence, b.avg_confidence),
        "avg_retry_delta": _delta(w.avg_retry_count, b.avg_retry_count),
        "avg_duration_delta": _delta(w.avg_duration_ms, b.avg_duration_ms),
        "avg_duration_ratio": duration_ratio,
    }


def find_component_concentration(window_events: list[OperationalEvent]) -> list[dict]:
    """Rank components by share of *failed* events in the window."""
    failed = [e for e in window_events if e.is_failure]
    counts: dict[str, int] = {}
    for e in failed:
        counts[e.component_id] = counts.get(e.component_id, 0) + 1
    return top_shares(counts)


def find_location_concentration(window_events: list[OperationalEvent]) -> list[dict]:
    failed = [e for e in window_events if e.is_failure]
    counts: dict[str, int] = {}
    for e in failed:
        counts[e.location_id] = counts.get(e.location_id, 0) + 1
    return top_shares(counts)


def find_event_type_concentration(window_events: list[OperationalEvent]) -> list[dict]:
    """Rank event types by share of *failed* events in the window.

    A window whose failures are dominated by one event type (e.g. system_alarm)
    points at a different failure mode than a mixed-failure window.
    """
    failed = [e for e in window_events if e.is_failure]
    counts: dict[str, int] = {}
    for e in failed:
        counts[e.event_type.value] = counts.get(e.event_type.value, 0) + 1
    return top_shares(counts)


def compare_event_type_duration(
    events: list[OperationalEvent],
    window_start: datetime,
    window_end: datetime,
    event_type: str,
) -> dict:
    """Compare avg duration_ms of one event type inside vs outside the window.

    Whole-stream average duration mixes fast and slow event types, so a large
    latency increase in one type can be diluted away. Comparing within the
    dominant failing event type isolates the latency signal.
    """
    in_window = [
        e for e in events
        if e.event_type.value == event_type and window_start <= e.timestamp < window_end
    ]
    baseline = [
        e for e in events
        if e.event_type.value == event_type
        and not (window_start <= e.timestamp < window_end)
    ]
    window_avg = sum(e.duration_ms for e in in_window) / len(in_window) if in_window else None
    baseline_avg = sum(e.duration_ms for e in baseline) / len(baseline) if baseline else None
    ratio = None
    if window_avg is not None and baseline_avg:
        ratio = round(window_avg / baseline_avg, 2)
    return {
        "event_type": event_type,
        "window_avg_ms": round(window_avg, 1) if window_avg is not None else None,
        "baseline_avg_ms": round(baseline_avg, 1) if baseline_avg is not None else None,
        "duration_ratio": ratio,
        "window_sample_size": len(in_window),
        "baseline_sample_size": len(baseline),
    }


def find_error_code_concentration(window_events: list[OperationalEvent]) -> list[dict]:
    counts: dict[str, int] = {}
    for e in window_events:
        if e.error_code:
            counts[e.error_code] = counts.get(e.error_code, 0) + 1
    return top_shares(counts)


def correlate_retry_count_and_confidence(window_events: list[OperationalEvent]) -> dict:
    """Pearson correlation between retry_count and confidence_score in the window.

    A strong negative correlation is evidence that retries are driven by low-quality
    reads rather than unrelated noise.
    """
    pairs = [
        (float(e.retry_count), e.confidence_score)
        for e in window_events
        if e.confidence_score is not None
    ]
    if len(pairs) < 3:
        return {"sample_size": len(pairs), "pearson_r": None, "interpretation": "insufficient data"}
    xs, ys = zip(*pairs)
    n = len(pairs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in pairs)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return {"sample_size": n, "pearson_r": None, "interpretation": "no variance"}
    r = cov / (vx**0.5 * vy**0.5)
    if r <= -0.5:
        interpretation = "strong negative correlation: retries track low confidence"
    elif r <= -0.2:
        interpretation = "moderate negative correlation"
    elif r >= 0.2:
        interpretation = "positive correlation (unexpected)"
    else:
        interpretation = "weak/no correlation"
    return {"sample_size": n, "pearson_r": round(r, 3), "interpretation": interpretation}


def build_timeline(
    window_events: list[OperationalEvent], bucket_minutes: int = 5
) -> dict:
    """Per-bucket failure counts inside the window, plus first/peak/last failure."""
    failures = sorted(
        (e for e in window_events if e.is_failure), key=lambda e: e.timestamp
    )
    entries = []
    for bucket_start, bucket in bucket_events(window_events, bucket_minutes):
        failed = sum(1 for e in bucket if e.is_failure)
        entries.append(
            {
                "bucket_start": bucket_start.isoformat(),
                "event_count": len(bucket),
                "failure_count": failed,
                "failure_rate": round(failed / len(bucket), 4) if bucket else 0.0,
            }
        )
    peak = max(entries, key=lambda x: x["failure_count"]) if entries else None
    return {
        "buckets": entries,
        "first_failure": failures[0].timestamp.isoformat() if failures else None,
        "last_failure": failures[-1].timestamp.isoformat() if failures else None,
        "peak_bucket": peak,
    }


def estimate_blast_radius(
    all_events: list[OperationalEvent], window_events: list[OperationalEvent]
) -> dict:
    failed = [e for e in window_events if e.is_failure]
    affected_correlations = {e.correlation_id for e in failed}
    window_correlations = {e.correlation_id for e in window_events}
    return {
        "window_event_count": len(window_events),
        "window_failure_count": len(failed),
        "affected_components": sorted({e.component_id for e in failed}),
        "affected_locations": sorted({e.location_id for e in failed}),
        "affected_correlation_ids": len(affected_correlations),
        "window_correlation_ids": len(window_correlations),
        "correlation_impact_share": (
            round(len(affected_correlations) / len(window_correlations), 4)
            if window_correlations
            else 0.0
        ),
        "share_of_total_traffic": (
            round(len(window_events) / len(all_events), 4) if all_events else 0.0
        ),
    }


HYPOTHESIS_MAX_SCORE = 10


def generate_hypothesis(evidence: dict) -> dict:
    """Rule-based root-cause hypothesis built strictly from computed evidence.

    Confidence is scored (0–10) from how strongly the evidence localizes the fault:
    component concentration, confidence drop, retry/confidence correlation,
    error-code dominance, duration inflation, and failed-event-type homogeneity.
    The failure-mode template (read quality / latency / alarm storm) is selected by
    which signals are present; if evidence does not localize the fault, the
    hypothesis says so.
    """
    comparison = evidence["baseline_vs_anomaly"]
    components = evidence["component_concentration"]
    locations = evidence["location_concentration"]
    error_codes = evidence["error_code_concentration"]
    correlation = evidence["retry_confidence_correlation"]
    event_types = evidence.get("event_type_concentration") or []

    top_component = components[0] if components else None
    top_location = locations[0] if locations else None
    top_error = error_codes[0] if error_codes else None
    top_event_type = event_types[0] if event_types else None
    confidence_delta = comparison.get("avg_confidence_delta")
    retry_delta = comparison.get("avg_retry_delta")
    # Duration compared within the dominant failing event type (see
    # compare_event_type_duration): the whole-window average would dilute it.
    type_duration = evidence.get("event_type_duration") or {}
    duration_ratio = type_duration.get("duration_ratio")

    score = 0
    reasoning = []
    if top_component and top_component["share"] >= 0.6:
        score += 2
        reasoning.append(
            f"{top_component['share']:.0%} of failures concentrate on a single "
            f"component ({top_component['key']}), indicating a localized fault "
            "rather than a systemic outage."
        )
    elif top_component:
        score += 1
        reasoning.append(
            f"Failures are only moderately concentrated (top component "
            f"{top_component['key']} at {top_component['share']:.0%})."
        )
    if confidence_delta is not None and confidence_delta <= -0.2:
        score += 2
        reasoning.append(
            f"Average confidence_score dropped by {abs(confidence_delta):.2f} vs "
            "baseline, consistent with degraded read quality."
        )
    if retry_delta is not None and retry_delta >= 0.5:
        score += 1
        reasoning.append(
            f"Average retry_count rose by {retry_delta:.2f} vs baseline."
        )
    r = correlation.get("pearson_r")
    if r is not None and r <= -0.5:
        score += 1
        reasoning.append(
            f"Retry count and confidence are strongly negatively correlated "
            f"(r={r}), so retries are driven by low-quality reads."
        )
    if top_error and top_error["share"] >= 0.5:
        score += 1
        reasoning.append(
            f"A single error code ({top_error['key']}) accounts for "
            f"{top_error['share']:.0%} of coded errors in the window."
        )
    if duration_ratio is not None and duration_ratio >= 2.0:
        score += 2
        reasoning.append(
            f"Average duration of {type_duration['event_type']} events in the window "
            f"is {duration_ratio:.1f}x baseline ({type_duration['baseline_avg_ms']:.0f} ms → "
            f"{type_duration['window_avg_ms']:.0f} ms), a substantial latency increase."
        )
    if top_event_type and top_event_type["share"] >= 0.8:
        score += 1
        reasoning.append(
            f"Window failures are homogeneous: {top_event_type['share']:.0%} are "
            f"{top_event_type['key']} events."
        )

    confidence = "high" if score >= 5 else "medium" if score >= 3 else "low"

    localized = top_component is not None and top_component["share"] >= 0.6
    location_part = f" at {top_location['key']}" if top_location else ""
    error_part = f" (dominant error: {top_error['key']})" if top_error else ""

    if localized and confidence_delta is not None and confidence_delta <= -0.2:
        failure_mode = "read_quality"
        hypothesis = (
            f"Localized read-quality degradation on {top_component['key']}"
            f"{location_part}: confidence collapsed while retries and failures "
            f"spiked on this component only{error_part}. Most consistent with a "
            "physical/optical or component-level fault (e.g. dirty or misaligned "
            "camera, lighting change, or degraded sensor) rather than an "
            "upstream/systemic failure."
        )
    elif (
        localized
        and top_event_type
        and top_event_type["key"] == "system_alarm"
        and top_event_type["share"] >= 0.6
    ):
        failure_mode = "alarm_storm"
        hypothesis = (
            f"Alarm storm from {top_component['key']}{location_part}: "
            f"{top_event_type['share']:.0%} of failed events in the window are "
            f"system_alarm events from this component{error_part}. Most consistent "
            "with a controller-level fault or a flapping/cascading alarm condition "
            "rather than independent downstream failures."
        )
    elif localized and duration_ratio is not None and duration_ratio >= 2.0:
        failure_mode = "latency"
        hypothesis = (
            f"Localized latency degradation on {top_component['key']}"
            f"{location_part}: average {type_duration['event_type']} duration rose "
            f"to {duration_ratio:.1f}x baseline while timeouts/failures spiked on "
            f"this component{error_part}. Most consistent with resource exhaustion, "
            "a queue backlog, or a capacity/configuration issue on the component "
            "rather than a data-quality fault."
        )
    elif top_component:
        failure_mode = "partial"
        hypothesis = (
            f"Elevated failure rate with partial concentration on "
            f"{top_component['key']}; evidence does not fully localize the fault. "
            "A component-level degradation is the leading candidate, but a shared "
            "upstream cause cannot be ruled out."
        )
    else:
        failure_mode = "diffuse"
        hypothesis = (
            "Failure rate spiked but no component concentration was found; the "
            "evidence points to a diffuse or systemic cause."
        )

    return {
        "hypothesis": hypothesis,
        "confidence": confidence,
        "score": score,
        "max_score": HYPOTHESIS_MAX_SCORE,
        "failure_mode": failure_mode,
        "reasoning": reasoning,
    }


def generate_recommended_actions(evidence: dict, hypothesis: dict) -> list[str]:
    components = evidence["component_concentration"]
    locations = evidence["location_concentration"]
    error_codes = evidence["error_code_concentration"]
    top_component = components[0]["key"] if components else "the affected component"
    top_location = locations[0]["key"] if locations else "the affected location"
    failure_mode = hypothesis.get("failure_mode")

    if failure_mode == "latency":
        actions = [
            f"Check load, queue depth, and resource utilization on {top_component} "
            f"at {top_location} for the anomaly window.",
            f"Review recent configuration, routing-table, or capacity changes for "
            f"{top_component} around the anomaly window start.",
            "Shift traffic to a healthy peer component (if one is available) until "
            "latency recovers.",
            "Monitor duration_ms and timeout rate on the affected component after "
            "intervention to confirm recovery against the baseline.",
        ]
    elif failure_mode == "alarm_storm":
        actions = [
            f"Inspect {top_component} at {top_location}: check controller state, "
            "error counters, and any recent restarts or firmware changes.",
            "Review the alarm sequence in the window to determine whether one root "
            "fault is cascading/flapping or multiple independent faults fired.",
            "Deduplicate or suppress the alarm flood if it risks masking other "
            "incidents, then address the root fault on the component.",
            "Monitor the system_alarm rate on the component after intervention to "
            "confirm recovery against the baseline.",
        ]
    else:
        actions = [
            f"Inspect {top_component} at {top_location}: check physical condition, "
            "alignment, lens/sensor cleanliness, and lighting.",
            f"Review component logs and recent configuration or firmware changes for "
            f"{top_component} around the anomaly window start.",
            "Temporarily route traffic away from the affected component (or enable the "
            "fallback/manual handling path) until read quality recovers.",
            "Monitor confidence_score and retry_count on the affected component after "
            "intervention to confirm recovery against the baseline.",
        ]
    if error_codes:
        actions.insert(
            2,
            f"Correlate the dominant error code ({error_codes[0]['key']}) with the "
            "component vendor's runbook / known failure modes.",
        )
    if hypothesis["confidence"] != "high":
        actions.append(
            "Evidence does not fully localize the fault: also check shared upstream "
            "dependencies (network segment, controller, power) for the window."
        )
    return actions
