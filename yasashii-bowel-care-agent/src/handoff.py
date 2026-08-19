from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_number} of {path}") from exc
        if isinstance(value, dict):
            records.append(value)
    return records


def build_summary(records: list[dict[str, Any]], target_date: str) -> dict[str, Any]:
    day_records = [
        record
        for record in records
        if str(record.get("timestamp", "")).startswith(target_date)
        and record.get("action") == "record_observation"
    ]
    amounts = Counter(str(record.get("amount", "unknown")) for record in day_records)
    return {
        "date": target_date,
        "observation_count": len(day_records),
        "relative_amount_counts": dict(sorted(amounts.items())),
        "note": (
            "Observation support only; this summary is not a medical diagnosis "
            "and does not prove that an unobserved bowel movement did not occur."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a privacy-minimized daily handoff summary.")
    parser.add_argument("--runtime-dir", default="runtime")
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()

    records = load_jsonl(Path(args.runtime_dir) / "event_log.jsonl")
    print(json.dumps(build_summary(records, args.date), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
