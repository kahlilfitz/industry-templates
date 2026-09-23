---
name: activity-pull
description: Retrieves engagement-scoped calendar, document activity, existing timesheet entries, billing guidelines and codes before narrative drafting. Use first when a user says "write up my time", "find my missing time", "what am I missing this week?", "prepare pre-bill hygiene", or asks to draft time from activity. This runs before `narrative-draft`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Delivery Billing Hygiene
---
# Activity Pull
## Purpose
Normalize the narrow set of activity and billing records needed for time-entry drafting: engagement calendar metadata, engagement-workspace document activity, existing time entries, client billing guidelines, and the illustrative task-code structure.
## When to use
Use first in the chain for requests such as "write up my time", "find missing time", "pull my week for this matter", "will these entries survive pre-bill?", or "prepare the engagement manager exception list".
## Inputs
Engagement identifier, date range, configured signal policy (`config/signal-sources.json`), timesheet export, client billing-guidelines extract, and task-code structure.
## Steps
1. Read `config/signal-sources.json` before retrieving activity.
2. Retrieve only enabled sources: by default, engagement-scoped calendar metadata and engagement-workspace document activity.
3. Keep mailbox content off unless the firm has explicitly enabled it for the matter.
4. Normalize signals and timesheet rows into `ps.time-expense-narrative-compliance.v1` with confidence, provenance and citations.
5. Hand the normalized packet to `narrative-draft`.
## Output
A contract-shaped activity packet containing `activity_signals[]`, `time_entries[]`, guideline references, code references and provenance.
## Grounding requirements
Every activity signal must cite its connector export or controlled repository extract. Calendar entries cite event metadata only; document activity cites file activity metadata, not document body.
## Constraints
- Privacy default is narrow by design: engagement-scoped calendar and document activity are on; mailbox content is off by default (`client-billing-guidelines.md #10.1`).
- Do not retrieve personal mailbox content, non-engagement calendars, unrelated workspace files or document bodies unless the firm config enables them.
- Draft-first: this skill reads and normalizes; it never submits time or edits WIP.
## Escalation / uncertainty
If a source is disabled, missing, or outside the engagement scope, state that the signal was excluded and continue with available cited sources. Low-confidence identity or matter matching must be held for review.
