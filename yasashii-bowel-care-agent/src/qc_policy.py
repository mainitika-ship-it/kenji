from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

ALLOWED_EVENTS = {"possible_bowel_event", "no_event", "unknown"}
ALLOWED_AMOUNTS = {"none", "small", "medium", "large", "unknown"}

Action = Literal[
    "record_observation",
    "request_caregiver_confirmation",
    "stop_and_check_signal",
]


@dataclass(frozen=True)
class ObservationEvent:
    """Privacy-minimized event emitted by the local vision layer."""

    timestamp: str
    event: str
    confidence: float
    changed_area_percent: float
    relative_amount: str
    signal_healthy: bool
    source: str = "simulated_test_data"
    contains_personal_data: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ObservationEvent":
        required = {
            "timestamp",
            "event",
            "confidence",
            "changed_area_percent",
            "relative_amount",
            "signal_healthy",
        }
        missing = sorted(required - raw.keys())
        if missing:
            raise ValueError(f"missing event fields: {', '.join(missing)}")

        timestamp = str(raw["timestamp"])
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be ISO 8601") from exc

        event = str(raw["event"])
        if event not in ALLOWED_EVENTS:
            raise ValueError(f"event must be one of: {', '.join(sorted(ALLOWED_EVENTS))}")

        confidence = float(raw["confidence"])
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

        changed_area_percent = float(raw["changed_area_percent"])
        if not 0.0 <= changed_area_percent <= 100.0:
            raise ValueError("changed_area_percent must be between 0 and 100")

        relative_amount = str(raw["relative_amount"])
        if relative_amount not in ALLOWED_AMOUNTS:
            raise ValueError(
                f"relative_amount must be one of: {', '.join(sorted(ALLOWED_AMOUNTS))}"
            )

        signal_healthy = raw["signal_healthy"]
        if not isinstance(signal_healthy, bool):
            raise ValueError("signal_healthy must be true or false")

        contains_personal_data = raw.get("contains_personal_data", False)
        if not isinstance(contains_personal_data, bool):
            raise ValueError("contains_personal_data must be true or false")

        source = str(raw.get("source", "simulated_test_data")).strip()
        if not source:
            raise ValueError("source must not be blank")

        return cls(
            timestamp=timestamp,
            event=event,
            confidence=confidence,
            changed_area_percent=changed_area_percent,
            relative_amount=relative_amount,
            signal_healthy=signal_healthy,
            source=source,
            contains_personal_data=contains_personal_data,
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ObservationEvent":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("event JSON must contain one object")
        return cls.from_dict(raw)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QCDecision:
    """QC control result passed to the Strands agent."""

    action: Action
    control_status: Literal["PASS", "HOLD", "STOP"]
    reasons: tuple[str, ...]
    confidence_threshold: float

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["reasons"] = list(self.reasons)
        return result


def evaluate_event(event: ObservationEvent, confidence_threshold: float = 0.80) -> QCDecision:
    """Apply a small, explainable QC control plan before agent orchestration."""

    if not 0.0 < confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be greater than 0 and at most 1")

    if event.contains_personal_data:
        return QCDecision(
            action="stop_and_check_signal",
            control_status="STOP",
            reasons=("personal_data_flag_is_true",),
            confidence_threshold=confidence_threshold,
        )

    if not event.signal_healthy:
        return QCDecision(
            action="stop_and_check_signal",
            control_status="STOP",
            reasons=("camera_or_signal_health_check_failed",),
            confidence_threshold=confidence_threshold,
        )

    hold_reasons: list[str] = []
    if event.event != "possible_bowel_event":
        hold_reasons.append("event_is_not_a_confirmed_possible_bowel_event")
    if event.confidence < confidence_threshold:
        hold_reasons.append("confidence_below_control_threshold")
    if event.relative_amount in {"none", "unknown"}:
        hold_reasons.append("relative_amount_requires_human_review")

    if hold_reasons:
        return QCDecision(
            action="request_caregiver_confirmation",
            control_status="HOLD",
            reasons=tuple(hold_reasons),
            confidence_threshold=confidence_threshold,
        )

    return QCDecision(
        action="record_observation",
        control_status="PASS",
        reasons=("all_critical_quality_checks_passed",),
        confidence_threshold=confidence_threshold,
    )
