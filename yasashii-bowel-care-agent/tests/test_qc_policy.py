from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qc_policy import ObservationEvent, evaluate_event


def make_event(**overrides):
    raw = {
        "timestamp": "2026-08-18T19:00:00+09:00",
        "event": "possible_bowel_event",
        "confidence": 0.92,
        "changed_area_percent": 10.0,
        "relative_amount": "medium",
        "signal_healthy": True,
        "source": "simulated_test_data",
        "contains_personal_data": False,
    }
    raw.update(overrides)
    return ObservationEvent.from_dict(raw)


def test_high_confidence_event_passes():
    decision = evaluate_event(make_event())
    assert decision.control_status == "PASS"
    assert decision.action == "record_observation"


def test_low_confidence_event_is_held():
    decision = evaluate_event(make_event(confidence=0.72))
    assert decision.control_status == "HOLD"
    assert decision.action == "request_caregiver_confirmation"


def test_unhealthy_signal_stops():
    decision = evaluate_event(make_event(signal_healthy=False))
    assert decision.control_status == "STOP"
    assert decision.action == "stop_and_check_signal"


def test_personal_data_flag_stops():
    decision = evaluate_event(make_event(contains_personal_data=True))
    assert decision.control_status == "STOP"
    assert decision.action == "stop_and_check_signal"


def test_no_event_is_not_silently_recorded_as_none():
    decision = evaluate_event(
        make_event(event="no_event", confidence=0.99, relative_amount="none")
    )
    assert decision.control_status == "HOLD"
    assert decision.action == "request_caregiver_confirmation"
