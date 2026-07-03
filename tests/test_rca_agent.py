import json

from click.testing import CliRunner

from opsflow.cli import main
from opsflow.data_gen.generator import write_events_jsonl
from opsflow.detection.anomaly_detector import detect_anomalies, write_anomalies_json
from opsflow.rca.diagnosis_agent import DiagnosisAgent
from opsflow.rca.report_writer import render_report

REQUIRED_SECTIONS = [
    "Incident summary",
    "Anomaly details",
    "Timeline",
    "Evidence",
    "Baseline vs anomaly comparison",
    "Root-cause hypothesis",
    "Confidence level",
    "Recommended actions",
    "Limitations / Assumptions",
]


def _diagnose(tmp_path, events):
    events_path = tmp_path / "events.jsonl"
    anomalies_path = tmp_path / "anomalies.json"
    write_events_jsonl(events, events_path)
    write_anomalies_json(detect_anomalies(events), anomalies_path)
    return DiagnosisAgent().diagnose_file(anomalies_path, events_path)


def test_diagnosis_evidence_matches_injected_scenario(tmp_path, spike_events):
    diagnoses = _diagnose(tmp_path, spike_events)
    assert len(diagnoses) == 1
    d = diagnoses[0]

    assert d.evidence["component_concentration"][0]["key"] == "OCR_GATE_02"
    assert d.evidence["location_concentration"][0]["key"] == "LOC_A02"
    assert d.evidence["error_code_concentration"][0]["key"] == "ERR_OCR_LOW_CONFIDENCE"
    assert d.evidence["baseline_vs_anomaly"]["avg_confidence_delta"] < -0.2
    assert d.evidence["baseline_vs_anomaly"]["avg_retry_delta"] > 0.5

    assert d.hypothesis["confidence"] == "high"
    assert "OCR_GATE_02" in d.hypothesis["hypothesis"]
    assert d.hypothesis["reasoning"], "hypothesis must cite evidence"
    assert len(d.recommended_actions) >= 3
    assert d.tool_log, "tool invocations must be traced"


def test_report_contains_required_sections(tmp_path, spike_events):
    diagnoses = _diagnose(tmp_path, spike_events)
    report = render_report(diagnoses, "events.jsonl", "anomalies.json")
    for section in REQUIRED_SECTIONS:
        assert section in report, f"missing section: {section}"
    assert "OCR_GATE_02" in report
    assert "deterministic" in report.lower()


def test_empty_anomalies_produce_clean_report(tmp_path, baseline_events):
    diagnoses = _diagnose(tmp_path, baseline_events)
    assert diagnoses == []
    report = render_report(diagnoses, "events.jsonl", "anomalies.json")
    assert "No anomalies were present" in report


def test_cli_end_to_end(tmp_path):
    runner = CliRunner()
    events = tmp_path / "events.jsonl"
    anomalies = tmp_path / "anomalies.json"
    report = tmp_path / "incident_report.md"

    result = runner.invoke(main, [
        "generate-events", "--count", "1000", "--scenario", "ocr_failure_spike",
        "--output", str(events), "--seed", "42",
        "--start-time", "2026-01-15T08:00:00+00:00",
    ])
    assert result.exit_code == 0, result.output
    assert events.exists()

    result = runner.invoke(main, [
        "detect-anomalies", "--input", str(events), "--output", str(anomalies),
    ])
    assert result.exit_code == 0, result.output
    doc = json.loads(anomalies.read_text())
    assert len(doc["anomalies"]) == 1

    result = runner.invoke(main, [
        "diagnose", "--input", str(anomalies), "--events", str(events),
        "--output", str(report),
    ])
    assert result.exit_code == 0, result.output
    content = report.read_text()
    assert "Root-cause hypothesis" in content
    assert "OCR_GATE_02" in content
