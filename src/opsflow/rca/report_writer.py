"""Markdown incident report renderer for RCA diagnoses."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opsflow.rca.diagnosis_agent import Diagnosis


def write_report(
    diagnoses: list[Diagnosis],
    output: Path,
    events_source: str,
    anomalies_source: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_report(diagnoses, events_source, anomalies_source), encoding="utf-8"
    )


def render_report(
    diagnoses: list[Diagnosis], events_source: str, anomalies_source: str
) -> str:
    lines = [
        "# Incident Report",
        "",
        f"- **Generated:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- **Events source:** `{events_source}`",
        f"- **Anomalies source:** `{anomalies_source}`",
        f"- **Anomalies diagnosed:** {len(diagnoses)}",
        "",
        "> All data in this report is synthetic. Diagnosis is produced by a "
        "deterministic, rule-based RCA workflow that inspects computed evidence — "
        "it is not an LLM.",
        "",
    ]
    if not diagnoses:
        lines += [
            "## Result",
            "",
            "No anomalies were present in the input; nothing to diagnose.",
            "",
        ]
        return "\n".join(lines)

    for diagnosis in diagnoses:
        lines += _render_diagnosis(diagnosis)

    lines += [
        "## Limitations / Assumptions",
        "",
        "- All events are synthetically generated; scenarios approximate real "
        "operational failure modes but are simplifications.",
        "- The RCA workflow is deterministic and rule-based: it localizes faults "
        "from statistical evidence (concentration, deltas, correlation) and maps "
        "them to known failure-mode templates. It cannot discover novel causes.",
        "- Detection uses per-bucket failure rates with robust statistics; short "
        "spikes below one bucket width or gradual degradations may be missed.",
        "- Baseline is derived from the non-anomalous part of the same stream; a "
        "fully degraded stream would weaken the comparison.",
        "",
    ]
    return "\n".join(lines)


def _render_diagnosis(d: Diagnosis) -> list[str]:
    a = d.anomaly
    metrics = a["metrics"]
    baseline = a["baseline_metrics"]
    comparison = d.evidence["baseline_vs_anomaly"]
    blast = d.evidence["blast_radius"]
    timeline = d.evidence["timeline"]
    top_component = _top(d.evidence["component_concentration"])
    top_location = _top(d.evidence["location_concentration"])

    lines = [
        f"## {a['anomaly_id']} — {a['type']} ({a['severity']})",
        "",
        "### Incident summary",
        "",
        f"Between **{a['window_start']}** and **{a['window_end']}**, the failure "
        f"rate rose to **{metrics['failure_rate']:.1%}** against a baseline of "
        f"**{baseline['failure_rate']:.1%}** "
        f"({metrics['failure_count']} failures across {metrics['event_count']} events). "
        + (
            f"Failures concentrated on **{top_component}** at **{top_location}**."
            if top_component
            else "Failures were not concentrated on a single component."
        ),
        "",
        "### Anomaly details",
        "",
        f"- Detection type: {a['type']}, peak robust z-score {a['peak_robust_z']}",
        f"- Window: {a['window_start']} → {a['window_end']}",
        f"- Severity: {a['severity']}",
        "",
        "### Timeline",
        "",
        f"- First failure in window: {timeline['first_failure']}",
        f"- Peak bucket: {timeline['peak_bucket']['bucket_start']} "
        f"({timeline['peak_bucket']['failure_count']} failures, "
        f"{timeline['peak_bucket']['failure_rate']:.1%} failure rate)"
        if timeline["peak_bucket"]
        else "- No failures recorded in window",
        f"- Last failure in window: {timeline['last_failure']}",
        "",
        "| Bucket start | Events | Failures | Failure rate |",
        "|---|---:|---:|---:|",
    ]
    for bucket in timeline["buckets"]:
        lines.append(
            f"| {bucket['bucket_start']} | {bucket['event_count']} | "
            f"{bucket['failure_count']} | {bucket['failure_rate']:.1%} |"
        )

    lines += [
        "",
        "### Baseline vs anomaly comparison",
        "",
        "| Metric | Baseline | Anomaly window | Delta |",
        "|---|---:|---:|---:|",
        f"| Failure rate | {comparison['baseline']['failure_rate']:.1%} | "
        f"{comparison['anomaly']['failure_rate']:.1%} | "
        f"{comparison['failure_rate_delta']:+.1%} |",
        f"| Avg confidence_score | {_fmt(comparison['baseline']['avg_confidence'])} | "
        f"{_fmt(comparison['anomaly']['avg_confidence'])} | "
        f"{_fmt(comparison['avg_confidence_delta'], signed=True)} |",
        f"| Avg retry_count | {comparison['baseline']['avg_retry_count']:.2f} | "
        f"{comparison['anomaly']['avg_retry_count']:.2f} | "
        f"{comparison['avg_retry_delta']:+.2f} |",
        f"| Avg duration_ms | {_fmt_ms(comparison['baseline']['avg_duration_ms'])} | "
        f"{_fmt_ms(comparison['anomaly']['avg_duration_ms'])} | "
        f"{_fmt_ms(comparison['avg_duration_delta'], signed=True)} |",
        "",
        "### Affected component / location (blast radius)",
        "",
        f"- Affected components: {', '.join(blast['affected_components']) or 'none'}",
        f"- Affected locations: {', '.join(blast['affected_locations']) or 'none'}",
        f"- Correlation IDs impacted: {blast['affected_correlation_ids']} of "
        f"{blast['window_correlation_ids']} in window "
        f"({blast['correlation_impact_share']:.1%})",
        f"- Window traffic share of total stream: {blast['share_of_total_traffic']:.1%}",
        "",
        "### Evidence",
        "",
        "**Failure concentration (share of failed events):**",
        "",
    ]
    for item in d.evidence["component_concentration"]:
        lines.append(f"- Component {item['key']}: {item['count']} failures ({item['share']:.0%})")
    for item in d.evidence["location_concentration"]:
        lines.append(f"- Location {item['key']}: {item['count']} failures ({item['share']:.0%})")
    for item in d.evidence.get("event_type_concentration", []):
        lines.append(f"- Event type {item['key']}: {item['count']} failures ({item['share']:.0%})")
    lines += ["", "**Error code concentration:**", ""]
    if d.evidence["error_code_concentration"]:
        for item in d.evidence["error_code_concentration"]:
            lines.append(f"- {item['key']}: {item['count']} ({item['share']:.0%})")
    else:
        lines.append("- No error codes recorded in window")

    correlation = d.evidence["retry_confidence_correlation"]
    lines += [
        "",
        "**Retry/confidence correlation:** "
        f"r={correlation['pearson_r']} over {correlation['sample_size']} events — "
        f"{correlation['interpretation']}",
        "",
        "**Tool invocations (diagnostic trace):**",
        "",
    ]
    for call in d.tool_log:
        lines.append(f"- `{call.tool}` → {call.summary}")

    lines += [
        "",
        "### Root-cause hypothesis",
        "",
        d.hypothesis["hypothesis"],
        "",
        f"**Confidence level:** {d.hypothesis['confidence']} "
        f"(evidence score {d.hypothesis['score']}/{d.hypothesis.get('max_score', 7)})",
        "",
        "Reasoning:",
        "",
    ]
    for reason in d.hypothesis["reasoning"]:
        lines.append(f"- {reason}")

    lines += ["", "### Recommended actions", ""]
    for i, action in enumerate(d.recommended_actions, start=1):
        lines.append(f"{i}. {action}")
    lines.append("")
    return lines


def _top(items: list[dict]) -> str | None:
    return items[0]["key"] if items else None


def _fmt(value, signed: bool = False) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.3f}" if signed else f"{value:.3f}"


def _fmt_ms(value, signed: bool = False) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.0f}" if signed else f"{value:.0f}"
