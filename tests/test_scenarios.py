"""End-to-end tests for the routing_latency_spike and alarm_storm scenarios.

Same shape as the ocr_failure_spike coverage: generation localizes the injection,
the detector finds the window, and the deterministic RCA produces the expected
failure mode with evidence-backed confidence.
"""

from datetime import datetime, timedelta

from opsflow.data_gen.generator import write_events_jsonl
from opsflow.data_gen.schemas import EventStatus, EventType, Severity
from opsflow.detection.anomaly_detector import detect_anomalies, write_anomalies_json
from opsflow.rca.diagnosis_agent import DiagnosisAgent
from opsflow.rca.report_writer import render_report
from tests.conftest import FIXED_START

# Injection windows as configured in scenarios.py (fractions of a 120-minute run).
ROUTING_WINDOW = (
    FIXED_START + timedelta(minutes=0.55 * 120),
    FIXED_START + timedelta(minutes=0.80 * 120),
)
ALARM_WINDOW = (
    FIXED_START + timedelta(minutes=0.40 * 120),
    FIXED_START + timedelta(minutes=0.65 * 120),
)


def _diagnose(tmp_path, events):
    events_path = tmp_path / "events.jsonl"
    anomalies_path = tmp_path / "anomalies.json"
    write_events_jsonl(events, events_path)
    write_anomalies_json(detect_anomalies(events), anomalies_path)
    return DiagnosisAgent().diagnose_file(anomalies_path, events_path)


def _assert_window_overlaps(anomaly: dict, injected: tuple[datetime, datetime]) -> None:
    start = datetime.fromisoformat(anomaly["window_start"])
    end = datetime.fromisoformat(anomaly["window_end"])
    assert start < injected[1] and end > injected[0]


# --- routing_latency_spike ---------------------------------------------------


def test_routing_injection_localizes_latency(routing_events):
    injected = [e for e in routing_events if e.metadata["injected_anomaly"]]
    assert injected, "scenario should inject anomalous events"
    assert {e.component_id for e in injected} == {"ROUTER_02"}
    assert {e.location_id for e in injected} == {"LOC_A03"}
    assert {e.event_type for e in injected} == {EventType.ROUTING_DECISION}
    # No confidence scores on routing events, failed ones time out.
    assert all(e.confidence_score is None for e in injected)
    failed = [e for e in injected if e.is_failure]
    assert failed and all(e.status == EventStatus.TIMEOUT for e in failed)

    # Injected routing decisions run several times slower than normal ones.
    normal_routing = [
        e for e in routing_events
        if e.event_type == EventType.ROUTING_DECISION and not e.metadata["injected_anomaly"]
    ]
    avg = lambda evts: sum(e.duration_ms for e in evts) / len(evts)  # noqa: E731
    assert avg(injected) > 3 * avg(normal_routing)


def test_routing_spike_detected(routing_events):
    result = detect_anomalies(routing_events)
    assert len(result["anomalies"]) == 1
    anomaly = result["anomalies"][0]
    _assert_window_overlaps(anomaly, ROUTING_WINDOW)
    assert anomaly["top_components"][0]["key"] == "ROUTER_02"
    assert anomaly["top_locations"][0]["key"] == "LOC_A03"
    assert anomaly["baseline_metrics"]["failure_rate"] < 0.1


def test_routing_diagnosis_identifies_latency(tmp_path, routing_events):
    diagnoses = _diagnose(tmp_path, routing_events)
    assert len(diagnoses) == 1
    d = diagnoses[0]

    assert d.hypothesis["failure_mode"] == "latency"
    assert d.hypothesis["confidence"] in {"medium", "high"}
    assert "ROUTER_02" in d.hypothesis["hypothesis"]
    assert d.hypothesis["reasoning"], "hypothesis must cite evidence"

    type_duration = d.evidence["event_type_duration"]
    assert type_duration["event_type"] == "routing_decision"
    assert type_duration["duration_ratio"] >= 2.0
    assert d.evidence["component_concentration"][0]["key"] == "ROUTER_02"
    assert len(d.recommended_actions) >= 3

    report = render_report(diagnoses, "events.jsonl", "anomalies.json")
    assert "ROUTER_02" in report and "Root-cause hypothesis" in report


# --- alarm_storm --------------------------------------------------------------


def test_alarm_injection_localizes_storm(alarm_events):
    injected = [e for e in alarm_events if e.metadata["injected_anomaly"]]
    assert injected, "scenario should inject anomalous events"
    assert {e.component_id for e in injected} == {"CONTROLLER_01"}
    assert {e.location_id for e in injected} == {"LOC_A01"}
    assert {e.event_type for e in injected} == {EventType.SYSTEM_ALARM}
    failed = [e for e in injected if e.is_failure]
    assert failed and all(e.severity == Severity.CRITICAL for e in failed)


def test_alarm_storm_detected(alarm_events):
    result = detect_anomalies(alarm_events)
    assert len(result["anomalies"]) == 1
    anomaly = result["anomalies"][0]
    _assert_window_overlaps(anomaly, ALARM_WINDOW)
    assert anomaly["top_components"][0]["key"] == "CONTROLLER_01"
    assert anomaly["baseline_metrics"]["failure_rate"] < 0.1


def test_alarm_diagnosis_identifies_storm(tmp_path, alarm_events):
    diagnoses = _diagnose(tmp_path, alarm_events)
    assert len(diagnoses) == 1
    d = diagnoses[0]

    assert d.hypothesis["failure_mode"] == "alarm_storm"
    assert d.hypothesis["confidence"] in {"medium", "high"}
    assert "CONTROLLER_01" in d.hypothesis["hypothesis"]
    assert d.hypothesis["reasoning"], "hypothesis must cite evidence"

    assert d.evidence["event_type_concentration"][0]["key"] == "system_alarm"
    assert d.evidence["event_type_concentration"][0]["share"] >= 0.6
    assert d.evidence["component_concentration"][0]["key"] == "CONTROLLER_01"
    assert len(d.recommended_actions) >= 3

    report = render_report(diagnoses, "events.jsonl", "anomalies.json")
    assert "CONTROLLER_01" in report and "system_alarm" in report
