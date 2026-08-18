# Architecture

```mermaid
flowchart LR
    A[Camera frame or safe simulated image] --> B[Local vision layer\nToilet-bowl ROI only\nSignal and lighting guard]
    B --> C[Structured event\nTimestamp\nPossible event\nConfidence\nChanged-area %\nRelative amount]
    C --> D[Strands Agents SDK\nReason over event data\nApply confidence policy\nChoose tool action]
    D -->|High confidence| E[Quiet observation record]
    D -->|Uncertain| F[Caregiver confirmation]
    E --> G[Event log]
    F --> G
    G --> H[Daily handoff summary]
```

## Boundary between pre-existing and hackathon work

**Pre-existing prototype, disclosed:** local toilet-water-region monitoring, possible-event detection, changed-area measurement, relative amount classification, CSV logging, privacy and signal guards.

**New during the hackathon:** Strands-based orchestration, confidence policy, human-confirmation flow, notifications, handoff summary, and the end-to-end agent behavior.

## Safety principles

- Public demos use safe simulated data.
- No medical diagnosis.
- No patient identity is needed by the agent.
- Raw images are not required once the local vision layer has produced a structured event.
- Uncertainty is escalated to a human rather than silently converted into a factual claim.
