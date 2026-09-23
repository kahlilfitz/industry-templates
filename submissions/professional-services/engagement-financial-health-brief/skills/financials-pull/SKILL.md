---
name: financials-pull
description: Pulls engagement financials, WIP ageing, billing, time, expense, plan, budget, rate-card and practice benchmark records into the ps.engagement-financial-health-brief.v1 contract. Use when the user says "how is this engagement doing?", "pull the engagement financials", "are we going to make our number?", "prep the practice review", or when an engagement financial health run begins.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Delivery Commercial Control
---
# Financials Pull
## Purpose
Assemble the grounded record base for the engagement: financial actuals, WIP and unbilled balances, time and expense, plan/budget, rate card, milestone status and benchmark definition metadata.

## When to use
Start every Engagement Financial Health Brief run here, before `health-calc`.

## Inputs
- Finance-system export: recognised revenue, billed revenue, billed labour revenue, delivery cost, standard value and unbilled balances.
- WIP ageing report with record ids, amounts and age in days.
- Timesheet extract with role, chargeable hours, available hours and cost-rate treatment.
- Engagement plan, budget, SOW economics, milestone plan and system ETC.
- Rate card and optional practice benchmark file.

## Steps
1. Verify engagement id, plan revision and review period match across sources.
2. Normalize records into the contract `ps.engagement-financial-health-brief.v1`; keep `source`, `citation`, `confidence` and `metric_definition_set_id` on the engagement and plan fields.
3. Preserve raw WIP record ids and ageing days. Do not net negative WIP against aged positive WIP.
4. Preserve benchmark `metric_definition_set_id`. Do not compare or normalize benchmark values here.
5. Hand the structured JSON inputs to `health-calc`.

## Output
Structured inputs for the shared contract: engagement, financials, WIP records, timesheets, plan/budget, rate card and optional benchmarks.

## Grounding requirements
Every extracted amount must cite the source export, row, report tab or plan section it came from. Every benchmark source must carry its definition-set id.

## Constraints
- No metric math here beyond faithful extraction and normalization.
- Never fill a missing definition id by guessing.
- Never change finance-system, PSA, time, billing or CRM records.

## Escalation / uncertainty
Stop the chain if engagement id, review period, currency, plan revision or definition set is inconsistent across the controlling inputs.
