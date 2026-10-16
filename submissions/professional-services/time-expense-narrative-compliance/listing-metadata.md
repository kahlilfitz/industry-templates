# Listing metadata draft: Time & Expense Narrative Compliance

Draft for the shared "Skills and Plugin Metadata Template" workbook. Not packaged. Values marked
"exactly as in the manifest" must stay in sync with `manifest.json`.

Plugin version: **1.0.13**, matching `manifest.json` and `metadata.json`.

## Name

- **name.short** (30/30): Time & Expense Narrative Check
- **name.full** (61/100): Time & Expense Narrative Compliance for Professional Services

## Description

**description.short** (69/80), exactly as in the manifest:

> Draft and check time-entry narratives for pre-bill; time entries only

**description.full**, exactly as in the manifest:

```text
Drafts and checks time-entry narratives: gathers cited calendar and document activity, drafts grounded narratives, recommends phase and task codes, checks client billing guidelines and missing time, and builds a draft pre-bill exception packet. Draft-first: it never submits time, approves a pre-bill or sends anything without explicit confirmation. Expense reports and receipts are out of scope.

Sign up: https://www.microsoft.com/en-us/copilot/pricing/enterprise
Get started: https://support.microsoft.com/en-us/microsoft-365-copilot/get-started-with-cowork
Help: https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/use-cowork
Contact us: https://support.microsoft.com/home/contact
```

## Category and industry

- **Category:** Accounting + finance; Workflow & Process Management; Productivity
- **Industry:** Professional Services

## Top 3 prompts

Each runs the main chain (activity-pull, narrative-draft, code-map, guideline-check,
exception-report).

1. Pull my calendar and document activity for the Orion billing controls engagement for last week,
   draft my time-entry narratives, map them to the client's phase and task codes and tell me which
   entries would be rejected under the billing guidelines.
2. I'm the engagement manager on ENG-SYN-042. Check the team's time for 14 to 18 September against
   the client billing guidelines, find any missing time and draft the pre-bill exception packet for
   the billing coordinator.
3. Write up my time for this week from my engagement calendar and workplan, flag block billing or
   vague wording, and show me what needs fixing before pre-bill.

## Conversation starters

1. Pull my activity for this matter
2. Draft my time entries for this week
3. Map my time to billing codes
4. Will this narrative get rejected?
5. Find my missing time
6. Show me the pre-bill exceptions

## Connectors (priority order)

1. Outlook calendar (engagement meeting metadata only: title, organizer, attendees, start, end)
2. SharePoint (engagement workspace document activity, workplan, engagement letter and client billing
   guidelines)
3. OneDrive (engagement document activity held by the timekeeper)
4. The firm's time and billing system (existing timesheet entries, task/phase code structure and
   WIP/pre-bill records; read only)
5. Microsoft Teams (meeting metadata for engagement meetings)

Mailbox content and mailbox metadata are off by default (`config/signal-sources.json` in each skill)
and need firm policy approval, matter scoping and user notice before they are enabled.

## Fluent icons

| Item | Fluent icon ID |
|---|---|
| Plugin | `ic_fluent_clock_24_regular` |
| activity-pull | `ic_fluent_calendar_arrow_down_24_regular` |
| narrative-draft | `ic_fluent_compose_24_regular` |
| code-map | `ic_fluent_tag_24_regular` |
| guideline-check | `ic_fluent_text_grammar_checkmark_24_regular` |
| exception-report | `ic_fluent_clipboard_error_24_regular` |

## Accent colour

`#7B3FA0`

## Per-skill compatibility (matches SKILL.md frontmatter)

| Skill | compatibility |
|---|---|
| activity-pull | Requires Python 3 (standard library only) to run scripts/activity_pull.py on user-supplied raw exports for one engagement (calendar, document activity, workplan and timesheet CSVs plus the engagement-letter extract); reads the config/signal-sources.json, contracts/ and references/ in this skill folder and writes activity.json locally. No connectors, network access or outbound actions; mailbox sources are off by default. |
| narrative-draft | Requires Python 3 (standard library only) to run scripts/narrative_draft.py on activity.json from activity-pull (plus the raw exports for a team view); reads the config/signal-sources.json, contracts/ and references/ in this skill folder and writes drafted.json locally. No connectors, network access or outbound actions. |
| code-map | Requires Python 3 (standard library only) to run scripts/code_map.py on drafted.json from narrative-draft and activity.json from activity-pull; reads the config/signal-sources.json, contracts/ and references/ (task-phase-codes.md) in this skill folder and writes coded.json locally. No connectors, network access or outbound actions. |
| guideline-check | Requires Python 3 (standard library only) to run scripts/guideline_check.py on coded.json from code-map and activity.json from activity-pull; reads the config/signal-sources.json, contracts/ and references/ (client-billing-guidelines.md) in this skill folder and writes governed.json locally. No connectors, network access or outbound actions. |
| exception-report | Requires Python 3 (standard library only) to run scripts/exception_report.py on governed.json from guideline-check and activity.json from activity-pull; reads the config/signal-sources.json, contracts/ and references/ in this skill folder and writes a local Markdown draft (exception-report.md). No connectors, network access or send capability. |

## Privacy and terms

- Privacy: https://privacy.microsoft.com/privacystatement
- Terms of use: https://www.microsoft.com/servicesagreement
- Developer website: https://www.microsoft.com/en-us/copilot/features/cowork
