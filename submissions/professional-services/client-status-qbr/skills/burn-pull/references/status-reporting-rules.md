# Status Reporting Rules - Client Status & QBR Assembly
Deterministic rules consumed by variance_calc.py and item_age.py. Engines cite these by
section number; constants in the engines mirror this document 1:1.

These excerpts are illustrative operating rules for demo grounding, not a reproduced client or
firm standard.

## 1. Evidence, confidence and provenance
| Rule | Condition | Effect |
|---|---|---|
| 1.1 | Every extracted plan, budget, risk, decision or action field | Preserve source system/file, citation and extraction confidence |
| 1.2 | Source values conflict across current plan, prior status and finance extract | Keep both values, prefer the system-of-record field for computation, and add an escalation |
| 1.3 | Any computed input confidence < 0.75 (CONFIDENCE_FLOOR) | Force the affected domain RAG to amber and require human review |

## 2. Schedule variance
| Rule | Condition | RAG / effect |
|---|---|---|
| 2.1 | Forecast variance from original baseline is > 5 calendar days (SCHEDULE_AMBER_DAYS) | Schedule RAG amber |
| 2.2 | Forecast variance from original baseline is > 10 calendar days (SCHEDULE_RED_DAYS) | Schedule RAG red |
| 2.3 | A milestone was re-baselined in the prior period | Do not accept the displayed green status until variance is recomputed against the original baseline |
| 2.4 | Forecast movement from the prior status pack is non-zero | Include period-over-period movement in the variance narrative |

## 3. Budget burn and forecast
| Rule | Condition | RAG / effect |
|---|---|---|
| 3.1 | Burn or forecast variance is >= 5% (BUDGET_AMBER_PCT) in either direction | Budget RAG amber. An underspend is escalated as such, not reported as favourable |
| 3.2 | Burn or forecast variance is >= 10% (BUDGET_RED_PCT) in either direction | Budget RAG red. State the direction of the variance, never just the colour |
| 3.3 | Unbilled WIP/accrual exists | Include WIP in actual burn before comparing to plan; billed-only burn is not authoritative |
| 3.4 | Forecast-to-complete changed since prior period, or no prior forecast was supplied | Include period-over-period forecast movement in the draft. Where no prior forecast exists the movement is unmeasurable and must be escalated, never reported as zero |

## 4. Scope and change control
| Rule | Condition | RAG / effect |
|---|---|---|
| 4.1 | One or more unapproved scope changes are open (SCOPE_AMBER_OPEN_ITEMS) | Scope RAG amber |
| 4.2 | Three or more unapproved scope changes are open, or any has client-facing impact | Scope RAG red |
| 4.3 | Scope impact is ambiguous, or an open change does not state whether it has client-facing impact | Keep as an escalation; do not call scope green. Confidence is judged over open changes only, so an approved low-confidence change does not drag current scope to amber |

## 5. Item ageing and ownership
| Rule | Condition | Effect |
|---|---|---|
| 5.1 | Open risk age >= 45 days (RISK_STALE_DAYS), or the RAID register is empty | Flag stale risk for re-rate. An empty register is escalated as a probable retrieval gap and must never be reported as "no open risks" |
| 5.2 | Open risk age >= 90 days (RISK_CRITICAL_DAYS) | Escalate aged risk in status pack and QBR narrative |
| 5.3 | Open decision age >= 7 days past due (DECISION_OVERDUE_DAYS) | Mark overdue decision and include in pending decisions |
| 5.4 | Open action age >= 7 days past due (ACTION_OVERDUE_DAYS) | Mark overdue action |
| 5.5 | Action is blocked by an *open* client decision, or has a client owner | Classify as pending client action even if the action owner was logged as internal. Once the blocking decision is approved or closed the action is no longer pending on the client and must be escalated for owner confirmation |

## 6. Roll-up status
| Rule | Condition | Effect |
|---|---|---|
| 6.1 | Overall RAG | Worst of schedule, budget and scope RAG using green < amber < red |
| 6.2 | Any open escalation from rules #1-#5 | Surface above the drafted narrative |

## 7. Draft-first boundary
| Rule | Condition | Effect |
|---|---|---|
| 7.1 | User asks to send, forward, share, post, file, upload, delete, approve, pay, reassign, update a system, re-baseline, close a risk or commit a date | Refuse the execution step and provide the draft/recommendation only, naming who should perform the action |
