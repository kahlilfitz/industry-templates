# Engagement Staffing & Bench Match

For resource managers, staffing partners, practice leads and delivery leads mobilising a signed engagement — especially when the bench is broad enough that "who comes to mind first" is no longer a defensible staffing method.

This template reads the engagement roles, bench roster, availability calendar, utilisation context, location and language data, rate bands and conflicts register. It scores candidate fit deterministically, ranks the slate, applies independence and availability constraints, and drafts a partner-ready recommendation where each number and refusal is cited to the underlying record or rule.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `role-intake` | Reads the signed engagement request, SOW role extract and start dates into the contract |
| 2 | `bench-query` | Normalises bench roster, skills, availability, utilisation, location, language and rate-band data |
| 3 | `fit-score` | Runs `fit_score` and `slate_rank` to compute component scores, utilisation context and provisional ranking |
| 4 | `constraint-check` | Runs `constraint_check`, the explicit Govern step, to refuse conflicted or unavailable candidates |
| 5 | `slate-draft` | Drafts the staffing recommendation, gap statement and approval notes from the governed payload |

The model extracts records, orchestrates the skills and writes cited prose. It never scores a candidate, ranks a slate, clears an independence issue or computes utilisation itself; those values come from deterministic Python engines.

## The case that shows why it exists

In the drama scenario, the obvious candidate is exactly who a staffer would reach for: perfect skills, the right seniority, local market experience, immediate system availability and a rate inside band. The fit engine ranks her first.

The Govern step refuses her anyway because the conflicts extract shows an unresolved material financial interest in the client. The same scenario includes a second trap: another candidate appears to have 0% allocation in the resource system, but an approved leave block plus a soft-booked pursuit makes them unavailable under the rule. The engine refuses both with the clauses cited and recommends the next eligible candidate, while a second role receives a gap statement because the eligible bench cannot cover it at the minimum score.

A naive slate picks the familiar perfect match. The rules engine does not.

## What you bring

A signed SOW or mobilisation request, role requirements and start dates, skills taxonomy, bench roster, availability and leave calendar, utilisation targets, rate card, location and language data, conflicts register and ethical-wall rules. The demo scenarios include raw staffing emails, SOW excerpts, bench CSV exports and conflicts extracts so the Connect path is exercised rather than assumed.

## Boundaries

Draft-first. The template recommends and explains; it does not assign a person, commit an allocation, override an independence flag, clear a conflict, change a rate or write back to the resource management system. Partner approval, independence clearance and staffing system updates remain human-controlled steps.

The reference excerpts are illustrative summaries for demo use. Replace them with your firm's controlled rules before production use.
