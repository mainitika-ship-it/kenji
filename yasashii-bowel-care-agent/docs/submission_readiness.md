# Agents for Humans Hackathon — Submission Readiness

Updated: 2026-08-21

This file is the project-side checklist for the final Devpost submission. It is intentionally conservative: an item is marked complete only when it has been verified, not merely planned.

## Required by the event

| Requirement | Status | Evidence / next action |
|---|---|---|
| Working agent built with Strands Agents SDK | IN PROGRESS | Agent and tools exist; live Bedrock three-case run still needs to be captured. |
| Public code repository | IN PROGRESS | Public project folder exists. Before final submission, confirm the final repository URL is judge-friendly. |
| README | DONE | Setup, architecture, safety, pre-existing disclosure, and demo commands are documented. |
| MIT or Apache license | DONE | MIT `LICENSE` is present in the project folder. |
| Architecture diagram | DONE | Devpost has the QC-oriented architecture image; Mermaid source is in `docs/architecture.md`. |
| Demo video, max 5 minutes | NOT STARTED | Record only after the live end-to-end flow is stable. See `docs/demo_storyboard.md`. |
| AWS Builder ID | DONE | Builder ID / alias was created and entered in Devpost. |
| Problem / audience / why it matters | DONE | Present in Devpost story and README. |

## Core implementation gate

Do not record the final video until all four checks below pass:

1. `python src/bedrock_preflight.py` returns `credentials_ok=true` and `bedrock_ok=true`.
2. `python src/demo.py --mode qc` shows PASS, HOLD, STOP in that order.
3. `python src/demo.py --mode live` causes Strands to call exactly one matching tool for each case.
4. A real local-vision structured event can be handed to the same agent interface without patient-identifying data.

## Judging alignment

### Technological Implementation

Priority evidence:

- explicit Strands Agents SDK use;
- Amazon Bedrock / Nova Lite model configuration;
- three real tool calls rather than a chat-only mockup;
- deterministic QC gate before model orchestration;
- live demonstration if possible.

Optional later: Bedrock AgentCore deployment.

### Design

Target one coherent caregiver experience:

`observe → QC decision → quiet record OR human confirmation → daily handoff`

Avoid adding unrelated features until this single loop is smooth.

### Potential Impact

Show the repetitive burden concretely: repeated checking, remembering, recording, and handing information to family or care professionals.

Use simulated data in the public demo. Do not expose real family care data.

### Creativity & Originality

Emphasize the combination of:

- privacy-minimized local sensing;
- QC-style PASS / HOLD / STOP controls;
- an agent that deliberately knows when **not** to decide;
- human-in-the-loop confirmation only when uncertainty requires it.

### Presentation

The final video must show the project actually working, not only slides. The pitch must clearly state:

1. the problem;
2. who it is for;
3. why it matters.

## Optional score boosters

Only after the required path is stable:

- public live demo link;
- Bedrock AgentCore deployment;
- builder.aws build-journey post.

## Do not do yet

- Do not upgrade AWS to a paid plan merely for dashboard widgets.
- Do not launch EC2, RDS, or other persistent services only to earn credits.
- Do not put AWS access keys, patient images, names, addresses, Wi-Fi data, or real care logs in GitHub.
- Do not claim clinical accuracy or diagnosis.
- Do not press final Devpost Submit until the public video and final repository are verified.
