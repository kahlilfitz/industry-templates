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

## Skills in this package

- **benchmark-compare** — Runs after health-calc and driver-attribute to compare health indicators against practice benchmarks only when the metric definition sets match. Use when the user asks "how does this compare to the practice?", "is this engagement above benchmark?", "show benchmark context", or after health-calc produces benchmark eligibility or refusal.
- **brief-draft** — Drafts the engagement financial health brief after health-calc, driver-attribute and benchmark-compare. Use when the user says "draft the brief", "write the engagement review", "prepare the practice review note", "summarize why margin is down", or "are we going to make our number?
- **driver-attribute** — Runs after health-calc to decompose the largest variance and rank the drivers with driver_attribute. Use when the user says "why is margin down?", "what is driving the variance?", "explain the WIP problem", "what changed versus plan?", or after health-calc flags amber or red indicators.
- **financials-pull** — Pulls engagement financials, WIP ageing, billing, time, expense, plan, budget, rate-card and practice benchmark records into the ps.engagement-financial-health-brief.v1 contract. Use when the user says "how is this engagement doing?", "pull the engagement financials", "are we going to make our number?", "prep the practice review", or when an engagement financial health run begins.
- **health-calc** — Runs after financials-pull to compute fixed-definition health indicators, RAG status, WIP ageing, unbilled exposure, burn, realisation, utilisation, ETC/EAC and early-warning flags with health_calc. Use when the user asks "what is the health?", "why does the dashboard say green?", "are we going to make our number?", "what is our WIP exposure?", or after the engagement records are pulled.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/engagement-financial-health-brief/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/engagement-financial-health-brief/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
