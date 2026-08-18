from __future__ import annotations

import argparse
import json
from pathlib import Path

from strands import Agent, tool


@tool
def record_observation(timestamp: str, amount: str, confidence: float, note: str = "") -> dict:
    """Prepare a privacy-minimized observation record for a caregiver log.

    Args:
        timestamp: Observation timestamp.
        amount: Relative amount label such as none, small, medium, large, or unknown.
        confidence: Confidence score between 0 and 1.
        note: Optional non-identifying note.
    """
    return {
        "action": "record_observation",
        "timestamp": timestamp,
        "amount": amount,
        "confidence": confidence,
        "note": note,
    }


@tool
def request_caregiver_confirmation(reason: str, suggested_amount: str = "unknown") -> dict:
    """Prepare a human-confirmation request for an uncertain observation.

    Args:
        reason: Why the observation needs human review.
        suggested_amount: Current relative-amount estimate, if any.
    """
    return {
        "action": "request_caregiver_confirmation",
        "reason": reason,
        "suggested_amount": suggested_amount,
    }


def build_agent() -> Agent:
    return Agent(
        system_prompt=(
            "You are a privacy-first family-care observation assistant. "
            "You do not diagnose disease and you never convert uncertainty into fact. "
            "The input is a structured observation produced by a local vision layer. "
            "If the event is clearly marked uncertain or confidence is below 0.80, "
            "use request_caregiver_confirmation. Otherwise use record_observation. "
            "Keep explanations short and respectful. Do not request or expose identities."
        ),
        tools=[record_observation, request_caregiver_confirmation],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, help="Path to a simulated structured-event JSON file")
    args = parser.parse_args()

    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    prompt = (
        "Process this non-identifying care observation. Choose the safest tool action. "
        "Do not make a medical diagnosis.\n\n"
        + json.dumps(event, ensure_ascii=False, indent=2)
    )

    agent = build_agent()
    result = agent(prompt)
    print(result)


if __name__ == "__main__":
    main()
