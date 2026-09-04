# Maintenance Triage

For the maintenance technician, reliability engineer or shift supervisor holding a fault that
needs a next action right now.

It reads the fault note, alarm codes and asset history, ranks the likely failure modes against
OEM manuals and past work orders, prioritises by asset criticality and downtime cost, and
drafts the work-order update with a recommended action. Documents are enough — a historian
feed is optional.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `fault-intake` | Reads fault notes, alarm and event logs, and the asset register into the contract |
| 2 | `history-retrieve` | Pulls prior work orders, similar failures, and the relevant OEM manual sections |
| 3 | `failure-mode-rank` | Ranks likely failure modes against symptoms, manual and history (deterministic) |
| 4 | `criticality-rank` | Prioritises by asset criticality × downtime cost (deterministic) |
| 5 | `work-order-update` | Drafts the work-order update and recommended action, cited |

Every hop carries data, confidence, provenance and citations through the
`mfg.maintenance-triage.v1` contract, so escalation is mechanical rather than a judgement call.

## The case that shows why it exists

Boiler feed water pump P-201 — criticality class A, $12,000/hour, no redundancy — "tripped on
overload again." The technician is about to do what worked the last three times: reset the
overload relay and move on. The alarm in front of them and the cheap fix agree.

Two facts change the answer:

- **History:** three motor-overload resets in 78 days.
- **A new signal:** a vibration alarm appeared for the first time this event, and vibration has
  been climbing across the quarter.

A repeat symptomatic fix is a signal, not a solution. The engine promotes bearing degradation
over the easy electrical reset and escalates the priority to P1.

## What you bring

The fault note or ticket, an alarm/event log, the asset register with criticality, and work-order
history. OEM manual excerpts help. Historian data is optional.

## Boundaries

Draft-first: the recommended action is a recommendation pending planner or supervisor approval,
and there is no CMMS write-back. This triages the fault in front of you — it does not forecast
future failures or optimise PM intervals.

Grounded in OEM manuals, CMMS work-order history, RCM and ISO 55000 — see `references/`.

## Skills in this package

- **criticality-rank** — Prioritizes the fault by asset criticality and downtime cost into a P1-P4 maintenance priority with a response target and cost estimate, deterministically. Use when the user says "how urgent is this", "what's the priority", "rank by criticality", "what will downtime cost", or after failure-mode-rank completes.
- **failure-mode-rank** — Ranks the likely failure modes for a fault against the failure-mode library, symptoms, alarm codes and repeat-failure history, deterministically. Use when the user says "what's the likely cause", "rank the failure modes", "diagnose this fault", "is this the real root cause?", or after history-retrieve completes.
- **fault-intake** — Reads maintenance fault notes, operator reports, alarm/event logs, asset IDs and location into the mfg.maintenance-triage.v1 contract inputs. Use when the user says "triage this fault", "work this breakdown", "read the fault note for <asset>", "what's wrong with pump <id>", or when a maintenance triage run begins.
- **history-retrieve** — Retrieves the asset's maintenance history — prior work orders, similar failures, PM records — and the relevant OEM manual and troubleshooting sections, and attaches them to the mfg.maintenance-triage.v1 contract. Use when the user says "pull the history for <asset>", "has this failed before?", "find the manual section", "any prior work orders?", or after fault-intake completes.
- **work-order-update** — Drafts the work-order update and recommended action from the triaged contract payload, with every determination cited to the manual, history and rules. Use when the user says "draft the work order", "write up the WO update", "what should we do", "recommend the fix", or after criticality-rank completes.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/maintenance-triage/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/maintenance-triage/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
