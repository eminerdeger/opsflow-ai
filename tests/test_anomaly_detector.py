from datetime import datetime, timedelta

from opsflow.detection.anomaly_detector import DetectorConfig, detect_anomalies
from tests.conftest import FIXED_START

# ocr_failure_spike injects into fractions 0.55–0.80 of a 120-minute run.
INJECTED_WINDOW_START = FIXED_START + timedelta(minutes=0.55 * 120)
INJECTED_WINDOW_END = FIXED_START + timedelta(minutes=0.80 * 120)


def test_detects_injected_spike(spike_events):
    result = detect_anomalies(spike_events)
    assert len(result["anomalies"]) == 1

    anomaly = result["anomalies"][0]
    assert anomaly["type"] == "failure_rate_spike"
    assert anomaly["severity"] in {"high", "critical"}

    # Detected window overlaps the injected window.
    start = datetime.fromisoformat(anomaly["window_start"])
    end = datetime.fromisoformat(anomaly["window_end"])
    assert start < INJECTED_WINDOW_END and end > INJECTED_WINDOW_START

    # Failure rate in the window is far above baseline.
    assert anomaly["metrics"]["failure_rate"] > 0.25
    assert anomaly["baseline_metrics"]["failure_rate"] < 0.1


def test_detected_anomaly_points_at_target_component(spike_events):
    anomaly = detect_anomalies(spike_events)["anomalies"][0]
    assert anomaly["top_components"][0]["key"] == "OCR_GATE_02"
    assert anomaly["top_locations"][0]["key"] == "LOC_A02"
    assert anomaly["top_error_codes"][0]["key"] == "ERR_OCR_LOW_CONFIDENCE"


def test_baseline_stream_has_no_anomalies(baseline_events):
    result = detect_anomalies(baseline_events)
    assert result["anomalies"] == []


def test_detector_config_is_applied(spike_events):
    # An absurdly high absolute floor suppresses detection entirely.
    result = detect_anomalies(spike_events, DetectorConfig(min_failure_rate=0.99))
    assert result["anomalies"] == []
