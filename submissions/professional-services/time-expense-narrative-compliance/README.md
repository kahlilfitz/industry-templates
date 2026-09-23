# Time & Expense Narrative Compliance

For consultants, billing coordinators and engagement managers who need time-entry narratives that can survive pre-bill and client guideline review.

The package drafts narratives from cited activity signals, maps them to the client's billing-code structure, then runs an explicit **Govern** step against billing guidelines: block billing, prohibited terms, vague wording, required detail, non-billable activity, duplicate meetings, increments, code mismatch and missing time. Govern is explicit because narrative compliance is a determination, not a style preference.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `activity-pull` | Retrieves engagement-scoped calendar/document activity, timesheet entries, guidelines and codes |
| 2 | `narrative-draft` | Drafts or preserves narrative prose from cited activity signals |
| 3 | `code-map` | Maps each entry to the illustrative phase/task code structure |
| 4 | `guideline-check` | Determines compliance - the Govern step - using deterministic rules |
| 5 | `exception-report` | Drafts the pre-bill exception and missing-time report |

## The case that shows why it exists

Scenario B includes entries that read fine at a skim and still fail deterministically:

- A polished 7.5-hour narrative combines four activity classes under one entry, triggering block-billing rejection.
- The same entry uses prohibited/vague phrases like "attention to", "various matters" and "review and revise".
- Two consultants enter the same meeting with the same narrative, so the second is a duplicate meeting exception.
- A plausible submitted task code maps to the wrong phase and is flagged for pre-bill recoding.
- Three hours of engagement document activity have no matching time entry and appear in the missing-time report.

A naive reviewer may accept the fluent prose; the engine does not.

## Privacy seam

`config/signal-sources.json` is part of the package on purpose. The default is the narrowest range that still works: engagement-scoped calendar metadata and engagement-workspace document activity are enabled, while mailbox content and mailbox metadata are off by default. A firm can explicitly enable more signals only with policy approval, matter scoping and user notice. This is a design feature, not a footnote.

## What you bring

Client billing guidelines, engagement-letter billing terms, task/phase code structure, engagement calendar metadata, document activity logs, existing timesheet entries, prior accepted narratives, WIP/pre-bill records and the firm's configured signal policy.

## Boundaries

Draft-first. It does not submit time, approve a pre-bill, write off WIP or bill a client. It prepares cited drafts and exception lists for human review by consultants, billing coordinators, engagement managers and revenue/WIP teams.
