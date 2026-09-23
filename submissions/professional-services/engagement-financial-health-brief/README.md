# Engagement Financial Health Brief

For engagement managers and practice leads who need one comparable read on engagement economics
without rebuilding a different spreadsheet for every client review.

This template pulls the financial record, WIP, unbilled time, expense, plan, budget and rate-card
inputs, computes health indicators on fixed definitions, compares the results with plan and
practice benchmarks, decomposes the largest variance arithmetically, and drafts a concise health
brief with the drivers cited. The value is not just speed; it is **definitional consistency**.
Realisation, utilisation, burn, WIP ageing and EAC mean the same thing every time the package runs.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `financials-pull` | Retrieves engagement financials, WIP, billing, time, expense, plan, budget, rate-card and benchmark records into the contract |
| 2 | `health-calc` | Runs `health_calc.py` to compute fixed-definition indicators, WIP ageing, unbilled exposure, ETC/EAC, early-warning flags and benchmark eligibility |
| 3 | `driver-attribute` | Runs `driver_attribute.py` to decompose the largest variance so the component drivers reconcile to the total variance |
| 4 | `benchmark-compare` | Surfaces practice benchmark comparisons only when the benchmark definition set matches the engagement definition set; otherwise it refuses |
| 5 | `brief-draft` | Drafts the engagement or practice review brief from engine output and citations |

Numbers and status calls come from deterministic Python engines (`health_calc`, `driver_attribute`).
The model retrieves, orchestrates and writes the cited prose. It never computes a figure, assigns a
RAG status, ranks a driver or repairs a benchmark mismatch.

## The case that shows why it exists

In the second demo scenario, the engagement looks fine if you stop at the usual summary:
margin is on plan, burn is on plan, billed revenue is on track and realisation clears the target.
A naive reviewer would keep the engagement green.

The fixed definitions expose the borrowed health:

- A large WIP balance is more than 90 days old, so collectability risk is no longer cosmetic.
- The staffing mix is junior-heavy. That flatters current margin, but the senior review hours the
  plan assumed have not been booked.
- A third of the due milestones have slipped, yet the system ETC was never revised.
- The practice benchmark supplied for the review uses a different utilisation definition, so the
  package refuses the comparison instead of manufacturing a flattering cross-engagement number.

The health brief is therefore amber/red even though individual headline indicators look green. The
driver engine reconciles the EAC cost variance arithmetically: actual burn variance plus system
remaining variance plus milestone slip remediation plus deferred senior review equals total EAC
variance. No "scope creep" guesswork is allowed.

## What you bring

Finance-system exports for recognised and billed revenue, WIP ageing, unbilled time and expense,
timesheet extracts, the engagement plan and budget, rate card, milestone status and practice
benchmark definitions. The demo scenarios include raw CSV-style extracts plus structured JSON so
you can exercise both the Connect path and the engines directly.

## Prerequisite: one definition set

This package depends on consistent metric definitions across the practice. If one team defines
utilisation as chargeable hours divided by gross capacity and another excludes training or bench
time from the denominator, the comparison is not safe. In that case, run the package as a
single-engagement health brief and leave practice benchmark comparison out of the configuration.

That refusal is intentional. `benchmark-compare` only compares engagements when the engagement,
package config and benchmark source share the same `metric_definition_set_id`. If they do not
match, the skill says why and stops the benchmark comparison rather than producing a misleading
number.

## Boundaries

Draft-first: the package reports, explains and drafts. It does not adjust WIP, write off balances,
change rates, revise a forecast, reallocate budget, invoice the client or write back to finance,
PSA, CRM or time-and-billing systems.

Grounded in the metric definitions and thresholds in `references/` and `config/`; replace those
with your controlled firm definitions before production use.
