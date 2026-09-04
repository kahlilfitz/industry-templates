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
