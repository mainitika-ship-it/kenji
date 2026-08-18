# Yasashii Bowel Care Agent

Privacy-first AI-agent prototype for family caregiving, prepared for the **Agents for Humans Hackathon**.

## Problem

Family caregivers may need to repeatedly check whether a bowel movement likely occurred, estimate its relative amount, record the event, and hand the information to other caregivers. This project explores how an agent can reduce that repetitive work while preserving human judgment and dignity.

## What this hackathon project adds

A basic local bowel-monitoring prototype existed before the hackathon. During the hackathon submission period, this project is adding a **Strands Agents SDK** workflow for:

- confidence-based decision making;
- quiet auto-recording of high-confidence events;
- caregiver confirmation for uncertain events;
- notification and daily handoff summaries;
- a clear human-in-the-loop safety policy.

Pre-existing work is disclosed rather than presented as new hackathon work.

## Privacy and safety

- No medical diagnosis.
- Public demos use simulated data, not real patient images.
- The design does not require faces or continuous video.
- Raw images should not be retained when a structured event is sufficient.
- Uncertain observations are escalated to a caregiver instead of being converted into a factual claim.

## Architecture

1. Camera frame or simulated test image
2. Local toilet-bowl-region computer vision
3. Structured event: timestamp, score/confidence, changed-area %, relative amount
4. Strands Agents SDK orchestration
5. High confidence → quiet record; uncertainty → caregiver confirmation
6. Event log and daily handoff summary

See `docs/architecture.md` for the Mermaid diagram.

## Quick start

Requires Python 3.10+ and AWS credentials suitable for the model provider used by Strands.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/agent.py --event sample_data/sample_event.json
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Current scope

The current public scaffold demonstrates the hackathon agent boundary using structured, simulated events. The image-detection layer will be brought across only after a privacy review removes personal/local configuration and confirms that no private care data is included.

## Built with

- Python
- Strands Agents SDK
- Computer vision / structured event inputs

## License

MIT License. See `LICENSE`.
