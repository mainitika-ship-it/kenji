from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from handoff import build_summary


def test_handoff_counts_only_recorded_observations_for_target_day():
    records = [
        {
            "action": "record_observation",
            "timestamp": "2026-08-21T08:00:00+09:00",
            "amount": "small",
        },
        {
            "action": "record_observation",
            "timestamp": "2026-08-21T18:00:00+09:00",
            "amount": "medium",
        },
        {
            "action": "request_caregiver_confirmation",
            "timestamp": "2026-08-21T19:00:00+09:00",
            "suggested_amount": "small",
        },
        {
            "action": "record_observation",
            "timestamp": "2026-08-20T20:00:00+09:00",
            "amount": "large",
        },
    ]

    summary = build_summary(records, "2026-08-21")
    assert summary["observation_count"] == 2
    assert summary["relative_amount_counts"] == {"medium": 1, "small": 1}
    assert "not a medical diagnosis" in summary["note"]


def test_empty_handoff_does_not_claim_no_bowel_movement():
    summary = build_summary([], "2026-08-21")
    assert summary["observation_count"] == 0
    assert summary["relative_amount_counts"] == {}
    assert "does not prove" in summary["note"]
