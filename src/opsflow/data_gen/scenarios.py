"""Config-driven anomaly scenarios.

Core generator logic stays scenario-agnostic; adding a new anomaly scenario means
adding an entry to SCENARIOS here, not touching generator code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from opsflow.data_gen.schemas import EventStatus, EventType, Severity


@dataclass(frozen=True)
class AnomalyScenario:
    """Parameters for one injected anomaly window inside an otherwise-normal stream."""

    name: str
    description: str
    # Anomaly window as fractions of the total generation timespan.
    window_start_frac: float
    window_end_frac: float
    # What the anomaly hits.
    target_event_type: EventType
    target_component: str
    target_location: str
    # Probability that an event inside the window is converted into an anomalous
    # event on the target component/location.
    anomaly_share: float
    # Behaviour of anomalous events.
    failure_rate: float
    # None means the target event type carries no confidence score (only OCR reads do).
    confidence_mean: float | None = None
    confidence_std: float = 0.0
    retry_min: int = 0
    retry_max: int = 0
    # Status/severity assigned to failed anomalous events.
    failed_status: EventStatus = EventStatus.FAILED
    failed_severity: Severity = Severity.ERROR
    # Multiplier applied to the target event type's normal duration profile.
    duration_multiplier: float = 1.0
    error_code_weights: dict[str, float] = field(default_factory=dict)


OCR_FAILURE_SPIKE = AnomalyScenario(
    name="ocr_failure_spike",
    description=(
        "Localized OCR read-failure spike on one gate: confidence collapses, retries "
        "climb, failures concentrate on a single component/location with a dominant "
        "error code."
    ),
    window_start_frac=0.55,
    window_end_frac=0.80,
    target_event_type=EventType.OCR_READ,
    target_component="OCR_GATE_02",
    target_location="LOC_A02",
    anomaly_share=0.55,
    failure_rate=0.85,
    confidence_mean=0.34,
    confidence_std=0.09,
    retry_min=2,
    retry_max=5,
    # Degraded reads run slow: roughly 3x the normal duration profile.
    duration_multiplier=3.0,
    error_code_weights={
        "ERR_OCR_LOW_CONFIDENCE": 0.7,
        "ERR_OCR_TIMEOUT": 0.3,
    },
)

ROUTING_LATENCY_SPIKE = AnomalyScenario(
    name="routing_latency_spike",
    description=(
        "Localized routing latency spike on one router: routing_decision duration "
        "climbs to several times baseline and a large share of decisions time out, "
        "concentrated on a single component/location."
    ),
    window_start_frac=0.55,
    window_end_frac=0.80,
    target_event_type=EventType.ROUTING_DECISION,
    target_component="ROUTER_02",
    target_location="LOC_A03",
    anomaly_share=0.55,
    failure_rate=0.70,
    retry_min=1,
    retry_max=3,
    failed_status=EventStatus.TIMEOUT,
    failed_severity=Severity.ERROR,
    # Routing decisions run ~8x slower inside the window (60ms profile → ~480ms).
    duration_multiplier=8.0,
    error_code_weights={
        "ERR_ROUTING_TIMEOUT": 0.65,
        "ERR_QUEUE_BACKLOG": 0.35,
    },
)

ALARM_STORM = AnomalyScenario(
    name="alarm_storm",
    description=(
        "Alarm storm from one controller: the window fills with failed system_alarm "
        "events of critical severity from a single component, with a dominant "
        "fault code."
    ),
    window_start_frac=0.40,
    window_end_frac=0.65,
    target_event_type=EventType.SYSTEM_ALARM,
    target_component="CONTROLLER_01",
    target_location="LOC_A01",
    anomaly_share=0.50,
    failure_rate=0.90,
    retry_min=0,
    retry_max=1,
    failed_status=EventStatus.FAILED,
    failed_severity=Severity.CRITICAL,
    error_code_weights={
        "ERR_CONTROLLER_FAULT": 0.6,
        "ERR_ALARM_FLOOD": 0.4,
    },
)

# name -> scenario; None means "baseline" (no anomaly injected).
SCENARIOS: dict[str, AnomalyScenario | None] = {
    "baseline": None,
    "ocr_failure_spike": OCR_FAILURE_SPIKE,
    "routing_latency_spike": ROUTING_LATENCY_SPIKE,
    "alarm_storm": ALARM_STORM,
}
