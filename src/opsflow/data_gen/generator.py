"""Deterministic synthetic event generator.

Produces a mostly-normal stream of operational events with an optional injected
anomaly window (see scenarios.py). Fully seeded: same (seed, scenario, count,
start_time, duration) → identical output, which makes the pipeline testable.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from opsflow.data_gen.scenarios import SCENARIOS, AnomalyScenario
from opsflow.data_gen.schemas import EventStatus, EventType, OperationalEvent, Severity

LOCATIONS = ["LOC_A01", "LOC_A02", "LOC_A03", "LOC_A04"]

COMPONENTS_BY_TYPE: dict[EventType, list[str]] = {
    EventType.BAGGAGE_SCAN: ["SORTER_01", "SORTER_02"],
    EventType.OCR_READ: ["OCR_GATE_01", "OCR_GATE_02"],
    EventType.ROUTING_DECISION: ["ROUTER_01", "ROUTER_02"],
    EventType.SYSTEM_ALARM: ["CONTROLLER_01"],
    EventType.PROCESSING_DELAY: ["SORTER_01", "ROUTER_01", "CONTROLLER_01"],
    EventType.RETRY_EVENT: ["OCR_GATE_01", "ROUTER_01", "SORTER_01"],
}

EVENT_TYPE_WEIGHTS: dict[EventType, float] = {
    EventType.BAGGAGE_SCAN: 0.30,
    EventType.OCR_READ: 0.30,
    EventType.ROUTING_DECISION: 0.20,
    EventType.PROCESSING_DELAY: 0.10,
    EventType.RETRY_EVENT: 0.05,
    EventType.SYSTEM_ALARM: 0.05,
}

# Typical processing duration per event type (mean ms, std ms).
DURATION_PROFILE: dict[EventType, tuple[int, int]] = {
    EventType.BAGGAGE_SCAN: (120, 40),
    EventType.OCR_READ: (250, 80),
    EventType.ROUTING_DECISION: (60, 20),
    EventType.SYSTEM_ALARM: (10, 5),
    EventType.PROCESSING_DELAY: (1800, 600),
    EventType.RETRY_EVENT: (400, 150),
}

NORMAL_ERROR_CODES = [
    "ERR_SCAN_NO_READ",
    "ERR_ROUTING_CONFLICT",
    "ERR_TRACKING_LOST",
    "ERR_COMPONENT_TIMEOUT",
]

NORMAL_FAILURE_RATE = 0.03


class EventGenerator:
    def __init__(
        self,
        seed: int = 42,
        scenario: str = "baseline",
        start_time: Optional[datetime] = None,
        duration_minutes: int = 120,
    ) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(
                f"Unknown scenario {scenario!r}. Available: {sorted(SCENARIOS)}"
            )
        self.rng = random.Random(seed)
        self.scenario: Optional[AnomalyScenario] = SCENARIOS[scenario]
        self.duration = timedelta(minutes=duration_minutes)
        if start_time is None:
            start_time = datetime.now(timezone.utc) - self.duration
        elif start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        self.start_time = start_time
        self._correlation_pool: list[str] = []

    def generate(self, count: int) -> list[OperationalEvent]:
        total_seconds = self.duration.total_seconds()
        offsets = sorted(self.rng.uniform(0, total_seconds) for _ in range(count))
        events = []
        for i, offset in enumerate(offsets):
            timestamp = self.start_time + timedelta(seconds=offset)
            frac = offset / total_seconds
            if self._in_anomaly_window(frac) and self.rng.random() < self.scenario.anomaly_share:
                events.append(self._anomalous_event(i, timestamp))
            else:
                events.append(self._normal_event(i, timestamp))
        return events

    def _in_anomaly_window(self, frac: float) -> bool:
        s = self.scenario
        return s is not None and s.window_start_frac <= frac <= s.window_end_frac

    def _normal_event(self, index: int, timestamp: datetime) -> OperationalEvent:
        rng = self.rng
        event_type = rng.choices(
            list(EVENT_TYPE_WEIGHTS), weights=list(EVENT_TYPE_WEIGHTS.values())
        )[0]
        component = rng.choice(COMPONENTS_BY_TYPE[event_type])
        location = rng.choice(LOCATIONS)
        failed = rng.random() < NORMAL_FAILURE_RATE
        status = (
            rng.choice([EventStatus.FAILED, EventStatus.TIMEOUT])
            if failed
            else EventStatus.SUCCESS
        )
        confidence = None
        if event_type == EventType.OCR_READ:
            base = 0.55 if failed else 0.93
            confidence = self._clamp(rng.gauss(base, 0.04), 0.05, 1.0)
        retry_count = 0
        if event_type == EventType.RETRY_EVENT:
            retry_count = rng.randint(1, 2)
        elif failed:
            retry_count = rng.randint(0, 1)
        return OperationalEvent(
            event_id=self._event_id(index),
            event_type=event_type,
            timestamp=timestamp,
            location_id=location,
            component_id=component,
            status=status,
            duration_ms=self._duration_ms(event_type),
            confidence_score=confidence,
            retry_count=retry_count,
            error_code=rng.choice(NORMAL_ERROR_CODES) if failed else None,
            severity=Severity.WARNING if failed else Severity.INFO,
            correlation_id=self._correlation_id(),
            metadata={"synthetic": True, "injected_anomaly": False},
        )

    def _anomalous_event(self, index: int, timestamp: datetime) -> OperationalEvent:
        rng = self.rng
        s = self.scenario
        failed = rng.random() < s.failure_rate
        status = s.failed_status if failed else EventStatus.SUCCESS
        error_code = None
        if failed:
            codes = list(s.error_code_weights)
            error_code = rng.choices(codes, weights=[s.error_code_weights[c] for c in codes])[0]
        confidence = None
        if s.confidence_mean is not None:
            confidence = self._clamp(rng.gauss(s.confidence_mean, s.confidence_std), 0.02, 0.65)
        mean_ms, std_ms = DURATION_PROFILE[s.target_event_type]
        return OperationalEvent(
            event_id=self._event_id(index),
            event_type=s.target_event_type,
            timestamp=timestamp,
            location_id=s.target_location,
            component_id=s.target_component,
            status=status,
            duration_ms=max(1, int(rng.gauss(mean_ms * s.duration_multiplier, std_ms))),
            confidence_score=confidence,
            retry_count=rng.randint(s.retry_min, s.retry_max),
            error_code=error_code,
            severity=s.failed_severity if failed else Severity.WARNING,
            correlation_id=self._correlation_id(),
            metadata={"synthetic": True, "injected_anomaly": True},
        )

    def _event_id(self, index: int) -> str:
        return f"EVT_{index:06d}_{self.rng.getrandbits(32):08x}"

    def _correlation_id(self) -> str:
        # ~30% of events attach to a recent journey; the rest start a new one.
        if self._correlation_pool and self.rng.random() < 0.3:
            return self.rng.choice(self._correlation_pool)
        cid = f"CORR_{self.rng.getrandbits(48):012x}"
        self._correlation_pool.append(cid)
        if len(self._correlation_pool) > 50:
            self._correlation_pool.pop(0)
        return cid

    def _duration_ms(self, event_type: EventType) -> int:
        mean_ms, std_ms = DURATION_PROFILE[event_type]
        return max(1, int(self.rng.gauss(mean_ms, std_ms)))

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        return round(max(lo, min(hi, value)), 4)


def write_events_jsonl(events: list[OperationalEvent], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(event.model_dump_json() + "\n")


def read_events_jsonl(path: Path) -> list[OperationalEvent]:
    events = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(OperationalEvent.model_validate_json(line))
    return events
