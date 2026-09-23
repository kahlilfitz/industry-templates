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

## Skills in this package

- **activity-pull** — Retrieves engagement-scoped calendar, document activity, existing timesheet entries, billing guidelines and codes before narrative drafting. Use first when a user says "write up my time", "find my missing time", "what am I missing this week?", "prepare pre-bill hygiene", or asks to draft time from activity. This runs before `narrative-draft`.
- **code-map** — Maps drafted time narratives to the client's phase and task code structure after `narrative-draft`. Use when the user asks "what code should this use?", "map my time to billing codes", "is this task code wrong?", or before checking whether a narrative will be rejected. Run before `guideline-check`.
- **exception-report** — Creates the engagement-manager pre-bill exception list after `guideline-check`. Use when the user says "show me the pre-bill exceptions", "what needs fixing before billing?", "summarize rejected narratives", "missing time report", or "send my billing coordinator the cleanup list".
- **guideline-check** — Governs drafted and coded time narratives against client billing guidelines after `code-map`. Use when the user asks "will this narrative get rejected?", "check billing guideline compliance", "catch block billing", "find prohibited terms", "what will pre-bill reject?", or "is this time compliant?" Run before `exception-report`.
- **narrative-draft** — Drafts or normalizes time-entry narrative prose from cited activity signals after `activity-pull`. Use when the user says "write up my time", "draft my time entries", "turn my calendar into narratives", or "make these entries client-ready". Run before `code-map`; the model may improve prose, but deterministic output and provenance stay fixed.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/time-expense-narrative-compliance/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/time-expense-narrative-compliance/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
