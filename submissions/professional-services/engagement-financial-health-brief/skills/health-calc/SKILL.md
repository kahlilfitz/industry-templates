---
name: health-calc
description: Runs after financials-pull to compute fixed-definition health indicators, RAG status, WIP ageing, unbilled exposure, burn, realisation, utilisation, ETC/EAC and early-warning flags with health_calc. Use when the user asks "what is the health?", "why does the dashboard say green?", "are we going to make our number?", "what is our WIP exposure?", or after the engagement records are pulled.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Health Calc
## Purpose
Deterministically compute the engagement health indicators using the configured threshold and metric-definition set.

## When to use
After `financials-pull`, before `driver-attribute` and `benchmark-compare`.

## Inputs
Structured JSON inputs from `financials-pull`, `config/thresholds.json`, and the contract in `contracts/`.

## Steps
1. Run `scripts/health_calc.py --engagement engagement.json --financials financials.json --wip wip.json --timesheets timesheets.json --plan plan_budget.json --rate-card rate_card.json --benchmarks benchmarks.json --config config/thresholds.json --out health.json`.
2. Quote indicator values, RAG status, early-warning flags and benchmark eligibility verbatim from `health.json`.
3. If `benchmark_comparison.status` is `refused`, preserve the refusal reason for `benchmark-compare`; do not calculate a benchmark delta in the model.
4. Pass `health.json` to `driver-attribute`.

## Output
`health.json` with indicators, WIP ageing, collectability reserve, ETC/EAC, composite status, early-warning flags, benchmark eligibility/refusal and provenance.

## Grounding requirements
Every indicator carries its metric definition section, metric definition set id, source, citation and confidence.

## Constraints
- All figures, thresholds, ageing buckets and RAG status are engine-only.
- The engine reads thresholds and definition metadata from `config/thresholds.json`; do not hard-code firm-specific definitions in prompts.
- No write-back, reforecast, WIP adjustment, rate change or budget reallocation.

## Escalation / uncertainty
If required inputs are missing, zero-denominator metrics are marked `not_evaluated` and the issue is passed as an escalation rather than smoothed over.
