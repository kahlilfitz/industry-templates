---
name: driver-attribute
description: Runs after health-calc to decompose the largest variance and rank the drivers with driver_attribute. Use when the user says "why is margin down?", "what is driving the variance?", "explain the WIP problem", "what changed versus plan?", or after health-calc flags amber or red indicators.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Delivery Commercial Control
---
# Driver Attribute
## Purpose
Decompose the largest engagement variance arithmetically and rank its drivers so the explanatory brief cites numbers that reconcile.

## When to use
After `health-calc` in every run, especially when health is amber/red or the user asks why a metric moved.

## Inputs
`health.json` from `health-calc`.

## Steps
1. Run `scripts/driver_attribute.py --health health.json --out drivers.json`.
2. Verify `driver_attribution.reconciles=true`. If false, surface the reconciliation delta and do not draft causal prose.
3. Quote driver amounts, ranks and citations verbatim. The model may explain the implications, but it never invents a driver.
4. Pass `drivers.json` to `benchmark-compare` and `brief-draft`.

## Output
`drivers.json` with largest variance, component table, driver ranks, reconciliation status, WIP reserve decomposition and escalations.

## Grounding requirements
Every driver cites the metric definition section and the source records carried in `health.json`.

## Constraints
- Drivers must sum to the total variance within rounding tolerance.
- "Scope creep", "poor management" or similar narrative causes cannot appear unless supported by an engine component.
- No reforecasting or budget reallocation.

## Escalation / uncertainty
If component totals do not reconcile, mark the attribution incomplete and require finance review before drafting the health brief.
