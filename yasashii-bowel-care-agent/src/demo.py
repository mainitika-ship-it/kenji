from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from agent import _build_prompt, build_agent
from model_config import resolve_bedrock_settings
from qc_policy import ObservationEvent, evaluate_event

DEFAULT_CASES = (
    "high_confidence_event.json",
    "uncertain_event.json",
    "bad_signal_event.json",
)


def load_case(path: Path, threshold: float) -> tuple[ObservationEvent, dict]:
    event = ObservationEvent.from_json_file(path)
    decision = evaluate_event(event, threshold)
    return event, decision.to_dict()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the three hackathon demo cases: PASS, HOLD, and STOP."
    )
    parser.add_argument(
        "--mode",
        choices=("qc", "live"),
        default="qc",
        help="qc = no model call; live = run through Strands + Bedrock",
    )
    parser.add_argument("--sample-dir", default="sample_data")
    parser.add_argument("--runtime-dir", default="runtime/demo")
    parser.add_argument("--confidence-threshold", type=float, default=0.80)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--region", default=None)
    args = parser.parse_args()

    sample_dir = Path(args.sample_dir)
    os.environ["YASASHII_RUNTIME_DIR"] = args.runtime_dir
    settings = resolve_bedrock_settings(args.model_id, args.region)

    print(
        json.dumps(
            {
                "demo_mode": args.mode,
                "model_id": settings.model_id,
                "region": settings.region_name,
                "cases": list(DEFAULT_CASES),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    agent = None
    if args.mode == "live":
        agent = build_agent(settings.model_id, settings.region_name)

    for filename in DEFAULT_CASES:
        path = sample_dir / filename
        event = ObservationEvent.from_json_file(path)
        decision = evaluate_event(event, args.confidence_threshold)
        print(f"\n=== {filename} -> {decision.control_status} ===")
        print(json.dumps(decision.to_dict(), ensure_ascii=False, indent=2))

        if agent is not None:
            result = agent(_build_prompt(event, decision))
            print(result)


if __name__ == "__main__":
    main()
