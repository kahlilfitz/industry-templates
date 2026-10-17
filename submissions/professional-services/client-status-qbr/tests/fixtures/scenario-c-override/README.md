# Scenario C — user threshold override (test fixture, not shipped)

This is `scenario-b-drama/status-input.json` plus a `settings` block that records a user request
made in conversation: budget red at 15% and a critical risk at 120 days
(status-reporting-rules.md #8.1).

Expected effect, captured in `expected/`:

| Item | Scenario B (defaults) | Scenario C (override) |
| --- | --- | --- |
| Budget RAG | Red (+13.6% ≥ 10%) | Amber (+13.6% < 15%) |
| R-401 (102 days) | Critical (≥ 90) | Stale (< 120) |
| Overall | Red | Red |
| Custom-threshold escalations | 0 | 2, one per changed value |

Regenerate from the package root:

```bash
python skills/variance-calc/scripts/variance_calc.py --input tests/fixtures/scenario-c-override/status-input.json --out tests/fixtures/scenario-c-override/expected/variance.json
python skills/risk-summarize/scripts/item_age.py --input tests/fixtures/scenario-c-override/expected/variance.json --out tests/fixtures/scenario-c-override/expected/aged.json
```
