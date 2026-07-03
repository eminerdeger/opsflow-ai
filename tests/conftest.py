from datetime import datetime, timezone

import pytest

from opsflow.data_gen.generator import EventGenerator

FIXED_START = datetime(2026, 1, 15, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def spike_events():
    """Deterministic ocr_failure_spike stream used across the test suite."""
    generator = EventGenerator(
        seed=42,
        scenario="ocr_failure_spike",
        start_time=FIXED_START,
        duration_minutes=120,
    )
    return generator.generate(1000)


@pytest.fixture
def baseline_events():
    generator = EventGenerator(
        seed=42,
        scenario="baseline",
        start_time=FIXED_START,
        duration_minutes=120,
    )
    return generator.generate(1000)


@pytest.fixture
def routing_events():
    """Deterministic routing_latency_spike stream."""
    generator = EventGenerator(
        seed=42,
        scenario="routing_latency_spike",
        start_time=FIXED_START,
        duration_minutes=120,
    )
    return generator.generate(1000)


@pytest.fixture
def alarm_events():
    """Deterministic alarm_storm stream."""
    generator = EventGenerator(
        seed=42,
        scenario="alarm_storm",
        start_time=FIXED_START,
        duration_minutes=120,
    )
    return generator.generate(1000)
