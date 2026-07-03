from datetime import timedelta

import pytest
from pydantic import ValidationError

from opsflow.data_gen.generator import (
    EventGenerator,
    read_events_jsonl,
    write_events_jsonl,
)
from opsflow.data_gen.schemas import EventType, OperationalEvent
from tests.conftest import FIXED_START


def test_generates_requested_count(spike_events):
    assert len(spike_events) == 1000


def test_events_are_valid_and_roundtrip(tmp_path, spike_events):
    path = tmp_path / "events.jsonl"
    write_events_jsonl(spike_events, path)
    loaded = read_events_jsonl(path)
    assert len(loaded) == len(spike_events)
    assert loaded[0] == spike_events[0]
    # Every line revalidates through the Pydantic schema.
    for line in path.read_text().splitlines():
        OperationalEvent.model_validate_json(line)


def test_schema_rejects_invalid_event():
    with pytest.raises(ValidationError):
        OperationalEvent(
            event_id="EVT_X",
            event_type="not_a_type",
            timestamp="2026-01-15T08:00:00Z",
            location_id="LOC_A01",
            component_id="OCR_GATE_01",
            status="success",
            duration_ms=-5,
            correlation_id="CORR_X",
        )


def test_deterministic_with_same_seed():
    kwargs = dict(scenario="ocr_failure_spike", start_time=FIXED_START, duration_minutes=120)
    a = EventGenerator(seed=7, **kwargs).generate(300)
    b = EventGenerator(seed=7, **kwargs).generate(300)
    assert [e.model_dump() for e in a] == [e.model_dump() for e in b]
    c = EventGenerator(seed=8, **kwargs).generate(300)
    assert [e.model_dump() for e in a] != [e.model_dump() for e in c]


def test_timestamps_sorted_and_in_range(spike_events):
    timestamps = [e.timestamp for e in spike_events]
    assert timestamps == sorted(timestamps)
    assert timestamps[0] >= FIXED_START
    assert timestamps[-1] <= FIXED_START + timedelta(minutes=120)


def test_anomaly_injection_localizes_failures(spike_events):
    injected = [e for e in spike_events if e.metadata["injected_anomaly"]]
    normal = [e for e in spike_events if not e.metadata["injected_anomaly"]]
    assert injected, "scenario should inject anomalous events"

    # Injected events target one component/location and one event type.
    assert {e.component_id for e in injected} == {"OCR_GATE_02"}
    assert {e.location_id for e in injected} == {"LOC_A02"}
    assert {e.event_type for e in injected} == {EventType.OCR_READ}

    # Injected events fail far more often, with lower confidence and more retries.
    injected_failure_rate = sum(e.is_failure for e in injected) / len(injected)
    normal_failure_rate = sum(e.is_failure for e in normal) / len(normal)
    assert injected_failure_rate > 0.6
    assert normal_failure_rate < 0.1

    injected_conf = [e.confidence_score for e in injected if e.confidence_score is not None]
    normal_conf = [e.confidence_score for e in normal if e.confidence_score is not None]
    assert sum(injected_conf) / len(injected_conf) < 0.5
    assert sum(normal_conf) / len(normal_conf) > 0.8
    assert all(e.retry_count >= 2 for e in injected)


def test_baseline_scenario_has_no_injection(baseline_events):
    assert not any(e.metadata["injected_anomaly"] for e in baseline_events)
    failure_rate = sum(e.is_failure for e in baseline_events) / len(baseline_events)
    assert failure_rate < 0.08


def test_unknown_scenario_rejected():
    with pytest.raises(ValueError, match="Unknown scenario"):
        EventGenerator(scenario="does_not_exist")
