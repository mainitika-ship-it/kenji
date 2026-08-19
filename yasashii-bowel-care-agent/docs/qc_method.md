# QC Method

Yasashii Bowel Care Agent uses an explainable control plan so that an AI model does not silently turn uncertainty into a care fact.

## CTQ: critical-to-quality conditions

The minimum conditions checked before the Strands agent acts are:

| Check | Why it matters | Failed result |
|---|---|---|
| `contains_personal_data == false` | Public and routine processing should not require identity data | STOP |
| `signal_healthy == true` | A blank, frozen, or failed camera signal must not create an event | STOP |
| `event == possible_bowel_event` | “No detection” must not be treated as proof of no bowel movement | HOLD |
| `confidence >= threshold` | Low-confidence observations require human judgment | HOLD |
| `relative_amount` is small/medium/large | Unknown or none needs review | HOLD |

When every CTQ check passes, the decision is **PASS** and the agent may record a privacy-minimized observation.

## Control states

### PASS

- Signal and privacy controls pass.
- Event and relative amount are valid.
- Confidence meets the configured threshold.
- Strands calls `record_observation`.

### HOLD

- The event is plausible but uncertain.
- Strands calls `request_caregiver_confirmation`.
- The caregiver can respond `Yes / No / Hold`.

### STOP

- Signal health or privacy control fails.
- Strands calls `stop_and_check_signal`.
- No care observation is automatically recorded.

## QC tools represented

- **Standardization:** one validated event schema and one decision vocabulary.
- **Check sheet:** JSONL actions preserve timestamp, amount, confidence, and reason.
- **Stratification:** PASS / HOLD / STOP separates safe automation from human review.
- **Trend review:** event logs can later be summarized by date and amount.
- **PDCA:** tests and simulated scenarios are used to adjust thresholds and improve the workflow.

## Current threshold

The default confidence threshold is `0.80`. It is a configurable engineering control, not a clinical accuracy claim. Camera-based testing and repeated simulated trials are required before any real-world operational threshold is selected.
