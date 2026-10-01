# Time & Expense Narrative Compliance

For consultants, billing coordinators and engagement managers who need time-entry narratives that can survive pre-bill and client guideline review.

The package builds a cited activity packet, drafts grounded narratives, maps them to the client's billing-code structure, then runs an explicit **Govern** step against billing guidelines: block billing, prohibited terms, vague wording, required detail, non-billable activity, duplicate meetings, increments, code mismatch and missing time. Govern is explicit because narrative compliance is a determination, not a style preference.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `activity-pull` | Builds a cited packet from enabled, engagement-scoped sources and records every privacy exclusion |
| 2 | `narrative-draft` | Drafts missing narratives and offers grounded rewrites beside preserved existing text |
| 3 | `code-map` | Maps unambiguous entries to phase/task codes and holds conflicting activity as `UNMAPPED` |
| 4 | `guideline-check` | Determines compliance using deterministic rules and verbatim, cited flags |
| 5 | `exception-report` | Writes a local draft pre-bill packet; it never sends or submits anything |

## The case that shows why it exists

Scenario B includes entries that read fine at a skim and still fail deterministically:

- A polished 7.5-hour narrative combines three activity classes under one entry, triggering block-billing rejection.
- The same entry uses prohibited/vague phrases like "attention to", "various matters" and "review and revise".
- Two consultants enter the same meeting with the same narrative, so the second is a duplicate meeting exception.
- A plausible submitted task code maps to the wrong phase and is flagged for pre-bill recoding.
- A link to disabled mailbox metadata is excluded from evidence, disclosed, and held for review.
- Three hours of engagement document activity have no matching time entry and appear in the missing-time report.

A naive reviewer may accept the fluent prose; the engine does not.

## Privacy seam

`config/signal-sources.json` is part of the package on purpose. Every engine enforces the narrowest effective policy from that file and the packet: engagement-scoped calendar metadata and engagement-workspace document activity are enabled, while mailbox content and mailbox metadata are off by default. If a skill runs without the plugin-level config, that same narrow default remains the mandatory floor, so a packet cannot enable mailbox access by itself. A `--signal-config` file is applied on top of the plugin config and can only narrow it. Disabled or unknown signals are removed from evidence and recorded under `provenance.excluded_signals`. A firm can explicitly enable broader sources only with policy approval, matter scoping and user notice.

## Timekeeper scope

Engines return only the requesting timekeeper's activity and time entries. Naming colleagues does not widen the scope. Other people's rows are released only in the engagement-manager team view: the requester must be the engagement manager recorded in the engagement letter, and the user must explicitly confirm the team view, which is passed as a structured `--team-view-confirmation engagement-manager:<engagement_id>` token. Role is never inferred from what a user says, and every downstream engine re-checks the recorded scope.

## Embedded instructions

Narrative, note, subject, deliverable, purpose, attendee and file-name text is data. A shared tripwire flags text that steers the reviewer or assistant, claims an approval or waiver, asks for forwarding, or carries an e-mail address or URL. Flagged text is held for review and withheld from drafts, suggested rewrites, missing-time listings and the exception packet (client-billing-guidelines.md #11).

## What you bring

Client billing guidelines, engagement-letter billing terms, task/phase code structure, engagement calendar metadata, document activity logs, existing timesheet entries, prior accepted narratives, WIP/pre-bill records and the firm's configured signal policy.

## Boundaries

Draft-first. It does not submit time, approve a pre-bill, alter WIP balances or bill a client. It does not handle expense reports, receipts or travel claims. Every skill follows the same recipient rule: drafts go only to the internal billing coordinator or engagement manager, never the client or any external address. If asked to share something, it prepares a draft, shows the internal recipients and content, and waits for explicit confirmation; if the internal recipient is unknown, it asks rather than guessing or looking one up. Exception-report owns refusals to submit time or approve a pre-bill.

The release bundle includes `tests/run_tests.py`, `tests/check_shared_copies.py` and the human spot-check prompt set so evaluators can reproduce the packaged engines and verify shared-file integrity.
