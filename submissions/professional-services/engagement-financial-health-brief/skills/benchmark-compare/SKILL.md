---
name: benchmark-compare
description: Runs after health-calc and driver-attribute to compare health indicators against practice benchmarks only when the metric definition sets match. Use when the user asks "how does this compare to the practice?", "is this engagement above benchmark?", "show benchmark context", or after health-calc produces benchmark eligibility or refusal.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Benchmark Compare
## Purpose
Add practice benchmark context when, and only when, the engagement and benchmark use the same metric definition set.

## When to use
After `health-calc` and `driver-attribute` whenever benchmark context is requested or available.

## Inputs
`drivers.json` or `health.json` containing `benchmark_comparison` from `health_calc`.

## Steps
1. Inspect `benchmark_comparison.status`.
2. If status is `compared`, quote the engine-provided benchmark deltas and citations verbatim.
3. If status is `refused`, refuse the comparison in plain language: the benchmark definition set does not match the engagement definition set, so cross-engagement comparison would be misleading.
4. Do not attempt to normalize utilisation, realisation or margin definitions in the model.

## Output
Benchmark context for the brief, or a benchmark refusal note with the reason and definition-set ids.

## Grounding requirements
Benchmark claims must cite the benchmark source, practice period and definition-set id. Refusals cite `engagement-financial-metric-definitions.md #1.1`.

## Constraints
- A benchmark definition mismatch is a feature, not an error to repair.
- If benchmark comparison is refused, continue the single-engagement health brief without benchmark deltas.
- No model-computed benchmark values.

## Escalation / uncertainty
If a benchmark source lacks a definition-set id, treat it as non-comparable and ask the practice operations owner to provide controlled definitions.
