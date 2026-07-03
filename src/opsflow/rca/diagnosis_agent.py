"""Deterministic RCA diagnosis workflow.

This is a tool-style diagnostic agent, NOT an LLM: it runs a fixed pipeline of
evidence-gathering tool functions (rca.tools) for each detected anomaly, records
every tool invocation for transparency, and derives a rule-based hypothesis whose
confidence reflects the strength of the computed evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from opsflow.data_gen.schemas import OperationalEvent
from opsflow.rca import tools


@dataclass
class ToolCall:
    tool: str
    summary: str


@dataclass
class Diagnosis:
    anomaly: dict
    evidence: dict
    hypothesis: dict
    recommended_actions: list[str]
    tool_log: list[ToolCall] = field(default_factory=list)


class DiagnosisAgent:
    """Runs the deterministic RCA tool pipeline for each detected anomaly."""

    def __init__(self, bucket_minutes: int = 5) -> None:
        self.bucket_minutes = bucket_minutes

    def diagnose_file(self, anomalies_path: Path, events_path: Path) -> list[Diagnosis]:
        anomalies_doc = json.loads(anomalies_path.read_text(encoding="utf-8"))
        events = tools.load_events(events_path)
        return [
            self.diagnose_anomaly(anomaly, events)
            for anomaly in anomalies_doc.get("anomalies", [])
        ]

    def diagnose_anomaly(
        self, anomaly: dict, events: list[OperationalEvent]
    ) -> Diagnosis:
        log: list[ToolCall] = []
        window_start = datetime.fromisoformat(anomaly["window_start"])
        window_end = datetime.fromisoformat(anomaly["window_end"])

        window_events = tools.filter_events_by_window(events, window_start, window_end)
        log.append(
            ToolCall(
                "filter_events_by_window",
                f"{len(window_events)} of {len(events)} events fall inside the anomaly window",
            )
        )

        comparison = tools.compare_baseline_vs_anomaly(events, window_start, window_end)
        log.append(
            ToolCall(
                "compare_baseline_vs_anomaly",
                f"failure rate {comparison['baseline']['failure_rate']:.1%} → "
                f"{comparison['anomaly']['failure_rate']:.1%}",
            )
        )

        components = tools.find_component_concentration(window_events)
        log.append(
            ToolCall(
                "find_component_concentration",
                f"top: {components[0]['key']} ({components[0]['share']:.0%} of failures)"
                if components
                else "no failed events in window",
            )
        )

        locations = tools.find_location_concentration(window_events)
        log.append(
            ToolCall(
                "find_location_concentration",
                f"top: {locations[0]['key']} ({locations[0]['share']:.0%} of failures)"
                if locations
                else "no failed events in window",
            )
        )

        error_codes = tools.find_error_code_concentration(window_events)
        log.append(
            ToolCall(
                "find_error_code_concentration",
                f"top: {error_codes[0]['key']} ({error_codes[0]['share']:.0%})"
                if error_codes
                else "no error codes in window",
            )
        )

        event_types = tools.find_event_type_concentration(window_events)
        log.append(
            ToolCall(
                "find_event_type_concentration",
                f"top: {event_types[0]['key']} ({event_types[0]['share']:.0%} of failures)"
                if event_types
                else "no failed events in window",
            )
        )

        type_duration = None
        if event_types:
            type_duration = tools.compare_event_type_duration(
                events, window_start, window_end, event_types[0]["key"]
            )
            log.append(
                ToolCall(
                    "compare_event_type_duration",
                    f"{type_duration['event_type']} avg duration "
                    f"{type_duration['baseline_avg_ms']} ms → {type_duration['window_avg_ms']} ms "
                    f"(ratio {type_duration['duration_ratio']})",
                )
            )

        correlation = tools.correlate_retry_count_and_confidence(window_events)
        log.append(
            ToolCall(
                "correlate_retry_count_and_confidence",
                f"r={correlation['pearson_r']} ({correlation['interpretation']})",
            )
        )

        timeline = tools.build_timeline(window_events, self.bucket_minutes)
        log.append(
            ToolCall(
                "build_timeline",
                f"{len(timeline['buckets'])} buckets; first failure "
                f"{timeline['first_failure']}",
            )
        )

        blast_radius = tools.estimate_blast_radius(events, window_events)
        log.append(
            ToolCall(
                "estimate_blast_radius",
                f"{blast_radius['window_failure_count']} failures across "
                f"{len(blast_radius['affected_components'])} component(s), "
                f"{blast_radius['affected_correlation_ids']} correlation id(s) affected",
            )
        )

        evidence = {
            "baseline_vs_anomaly": comparison,
            "component_concentration": components,
            "location_concentration": locations,
            "error_code_concentration": error_codes,
            "event_type_concentration": event_types,
            "event_type_duration": type_duration,
            "retry_confidence_correlation": correlation,
            "timeline": timeline,
            "blast_radius": blast_radius,
        }

        hypothesis = tools.generate_hypothesis(evidence)
        log.append(
            ToolCall(
                "generate_hypothesis",
                f"confidence={hypothesis['confidence']} (evidence score {hypothesis['score']})",
            )
        )

        actions = tools.generate_recommended_actions(evidence, hypothesis)
        log.append(ToolCall("generate_recommended_actions", f"{len(actions)} actions"))

        return Diagnosis(
            anomaly=anomaly,
            evidence=evidence,
            hypothesis=hypothesis,
            recommended_actions=actions,
            tool_log=log,
        )
