from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from strands import Agent, tool

from qc_policy import ObservationEvent, QCDecision, evaluate_event


def _runtime_file(filename: str) -> Path:
    directory = Path(os.environ.get("YASASHII_RUNTIME_DIR", "runtime"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory / filename


def _append_jsonl(filename: str, payload: dict[str, Any]) -> str:
    path = _runtime_file(filename)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return str(path)


@tool
def record_observation(
    timestamp: str,
    amount: str,
    confidence: float,
    changed_area_percent: float,
    note: str = "",
) -> dict[str, Any]:
    """Record a privacy-minimized, high-confidence observation.

    Args:
        timestamp: Observation timestamp in ISO 8601 form.
        amount: Relative amount label: small, medium, or large.
        confidence: Confidence score between 0 and 1.
        changed_area_percent: Changed area in the configured region of interest.
        note: Optional non-identifying note.
    """
    payload = {
        "action": "record_observation",
        "timestamp": timestamp,
        "amount": amount,
        "confidence": confidence,
        "changed_area_percent": changed_area_percent,
        "note": note,
        "recorded_at": datetime.now().astimezone().isoformat(),
    }
    payload["log_path"] = _append_jsonl("event_log.jsonl", payload)
    return payload


@tool
def request_caregiver_confirmation(
    timestamp: str,
    reason: str,
    suggested_amount: str = "unknown",
) -> dict[str, Any]:
    """Queue an uncertain event for a caregiver's Yes / No / Hold decision.

    Args:
        timestamp: Observation timestamp in ISO 8601 form.
        reason: Short explanation of why human review is required.
        suggested_amount: Current relative-amount estimate, if available.
    """
    payload = {
        "action": "request_caregiver_confirmation",
        "timestamp": timestamp,
        "reason": reason,
        "suggested_amount": suggested_amount,
        "queued_at": datetime.now().astimezone().isoformat(),
    }
    payload["queue_path"] = _append_jsonl("confirmation_queue.jsonl", payload)
    return payload


@tool
def stop_and_check_signal(timestamp: str, reason: str) -> dict[str, Any]:
    """Stop automatic recording when privacy or signal-health controls fail.

    Args:
        timestamp: Observation timestamp in ISO 8601 form.
        reason: Failed safety or quality control.
    """
    payload = {
        "action": "stop_and_check_signal",
        "timestamp": timestamp,
        "reason": reason,
        "raised_at": datetime.now().astimezone().isoformat(),
    }
    payload["alert_path"] = _append_jsonl("system_alerts.jsonl", payload)
    return payload


def build_agent() -> Agent:
    return Agent(
        system_prompt=(
            "You are a privacy-first family-care observation agent. "
            "You do not diagnose disease and you never convert uncertainty into fact. "
            "The user supplies both a structured observation and an explainable QC decision. "
            "Follow the QC action exactly: PASS uses record_observation; "
            "HOLD uses request_caregiver_confirmation; STOP uses stop_and_check_signal. "
            "Call exactly one tool. Never request or expose a person's identity. "
            "Keep any explanation short and respectful."
        ),
        tools=[
            record_observation,
            request_caregiver_confirmation,
            stop_and_check_signal,
        ],
    )


def _build_prompt(event: ObservationEvent, decision: QCDecision) -> str:
    return (
        "Process this non-identifying care observation. "
        "Call exactly the tool required by the QC decision. "
        "Do not make a medical diagnosis.\n\n"
        f"EVENT:\n{json.dumps(event.to_dict(), ensure_ascii=False, indent=2)}\n\n"
        f"QC DECISION:\n{json.dumps(decision.to_dict(), ensure_ascii=False, indent=2)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Yasashii Bowel Care Agent on a structured event."
    )
    parser.add_argument("--event", required=True, help="Structured-event JSON file")
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.80,
        help="QC threshold between 0 and 1 (default: 0.80)",
    )
    parser.add_argument(
        "--runtime-dir",
        default="runtime",
        help="Local directory for logs and confirmation queues",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the QC decision without calling a model",
    )
    args = parser.parse_args()

    os.environ["YASASHII_RUNTIME_DIR"] = args.runtime_dir
    event = ObservationEvent.from_json_file(args.event)
    decision = evaluate_event(event, args.confidence_threshold)

    if args.dry_run:
        print(
            json.dumps(
                {"event": event.to_dict(), "qc_decision": decision.to_dict()},
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    agent = build_agent()
    result = agent(_build_prompt(event, decision))
    print(result)


if __name__ == "__main__":
    main()
