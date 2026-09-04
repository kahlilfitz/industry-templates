# Production Planning

For the planner who has to publish a shift plan on Friday and knows that the spreadsheet's
"84% loaded" is not the same thing as a plan that will actually run.

It pulls the demand forecast and open orders, checks capacity, constraints and material
availability, sequences the week to minimise changeovers with a deterministic campaign
heuristic, and drafts the shift plan for the planner to publish.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `demand-pull` | Pulls the demand forecast and open orders into the contract |
| 2 | `capacity-check` | Checks work-centre capacity, constraints and material availability (deterministic) |
| 3 | `schedule-optimize` | Sequences for changeovers with a campaign heuristic (deterministic) |
| 4 | `shift-plan-draft` | Drafts the shift plan for the planner to publish |

## The case that shows why it exists

"84% loaded, run it by due date." Three things that number hides:

- The naive due-date sequence alternates product families — pump, valve, pump, valve — and burns
  **more than ten hours** in changeovers. Run-hours utilisation is not a plan.
- One committed order is material-gated until Wednesday.
- Between the changeovers and the gate, the naive sequence finishes a **committed customer
  order late**.

The engine reports the naive miss, produces a campaign sequence that protects both committed
orders, drops the changeover hours, and names the material gate in the escalation.

## What you bring

The demand plan and open orders, work-centre capacity, the changeover matrix and material
availability. JSON or spreadsheet exports both work.

## Boundaries

Draft-first: the shift plan is a draft for the planner to review and publish. This is a
heuristic sequencer, not a solver — connecting a live APS or optimisation engine is the
graduation step.

Grounded in the scheduling rules in `references/` — replace them with your own.

## Skills in this package

- **capacity-check** — Checks capacity, constraints and material availability for the plan week with the deterministic capacity_check engine. Use when the user says "do we have capacity", "does the week fit", "check materials", or after demand-pull in a planning run.
- **demand-pull** — Pulls the demand forecast and open orders for the plan week into the mfg.production-planning.v1 contract. Use when the user says "plan next week", "build the schedule", "pull the orders for line <x>", or when a planning run begins.
- **schedule-optimize** — Optimizes the weekly sequence for changeovers with the deterministic campaign heuristic - naive vs optimized compared side by side - using the sequence_optimize engine. Use when the user says "optimize the schedule", "sequence the week", "minimize changeovers", or after capacity-check in a planning run.
- **shift-plan-draft** — Drafts the shift plan from the optimized schedule for the planner to review and publish. Use when the user says "draft the shift plan", "write up the week", "publish the plan" (which produces the draft), or after schedule-optimize in a planning run.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/production-planning/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/production-planning/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
