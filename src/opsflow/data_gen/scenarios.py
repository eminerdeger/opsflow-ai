"""Config-driven anomaly scenarios.

Core generator logic stays scenario-agnostic; adding a new anomaly scenario means
adding an entry to SCENARIOS here, not touching generator code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from opsflow.data_gen.schemas import EventType


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
    confidence_mean: float
    confidence_std: float
    retry_min: int
    retry_max: int
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
    error_code_weights={
        "ERR_OCR_LOW_CONFIDENCE": 0.7,
        "ERR_OCR_TIMEOUT": 0.3,
    },
)

# name -> scenario; None means "baseline" (no anomaly injected).
SCENARIOS: dict[str, AnomalyScenario | None] = {
    "baseline": None,
    "ocr_failure_spike": OCR_FAILURE_SPIKE,
}
