"""Pydantic schemas for synthetic operational events.

The event model is generic (high-volume operational telemetry); the demo domain is
airport/logistics-style baggage handling, but nothing here is tied to a real system.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    BAGGAGE_SCAN = "baggage_scan"
    OCR_READ = "ocr_read"
    ROUTING_DECISION = "routing_decision"
    SYSTEM_ALARM = "system_alarm"
    PROCESSING_DELAY = "processing_delay"
    RETRY_EVENT = "retry_event"


class EventStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


FAILURE_STATUSES = {EventStatus.FAILED, EventStatus.TIMEOUT}


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class OperationalEvent(BaseModel):
    event_id: str
    event_type: EventType
    timestamp: datetime
    location_id: str
    component_id: str
    status: EventStatus
    duration_ms: int = Field(ge=0)
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    retry_count: int = Field(default=0, ge=0)
    error_code: Optional[str] = None
    severity: Severity = Severity.INFO
    correlation_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_failure(self) -> bool:
        return self.status in FAILURE_STATUSES
