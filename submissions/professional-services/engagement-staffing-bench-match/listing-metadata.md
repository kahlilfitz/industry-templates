# Listing metadata draft: Engagement Staffing & Bench Match 1.1.7

Draft for the shared "Skills and Plugin Metadata Template" workbook. Not packaged. The manifest
values below are copied exactly from `manifest.json`.

## Name

- **name.short** (22/30): Staffing & Bench Match
- **name.full** (33/100): Engagement Staffing & Bench Match

## Description

- **description.short** (75/80): Engagement staffing: bench fit scores, independence checks and slate drafts
- **description.full** (646/4000):

```text
Builds a ranked staffing slate for a signed engagement from the SOW, bench roster, availability, rates and conflicts register. Engines score fit and refuse conflicted or unavailable candidates, citing the rule. Draft-first: it drafts a partner recommendation and never approves, allocates or assigns staff, changes rates or overrides independence.

Sign up: https://www.microsoft.com/en-us/copilot/pricing/enterprise
Get started: https://support.microsoft.com/en-us/microsoft-365-copilot/get-started-with-cowork
Help: https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/use-cowork
Contact us: https://support.microsoft.com/home/contact
```

## Category and Industry

- **Category:** Project management; Legal + HR; Productivity
- **Industry:** Professional Services

## Top 3 prompts

1. New engagement signed for Orchard Ridge Clinics. Staff this SOW from the attached bench export and conflicts extract, and draft the partner approval note.
2. Build me a slate for the Aster Foods finance transformation manager and workforce planning roles. Mina looks perfect; check independence and availability before you recommend anyone.
3. Who is available and the best fit for the data migration consultant role starting 12 October? Check conflicts and draft the staffing recommendation.

## Conversation starters

1. Start a staffing slate from this SOW
2. Who on the bench is available for these roles?
3. Rank the bench for the open roles
4. Is anyone conflicted for this engagement?
5. Why can't we use the top match?
6. Draft the partner approval note

## Connectors (priority order)

The skills read user-supplied exports today and call no connector. These are the systems those
exports come from:

1. SharePoint / OneDrive: signed SOW and role extracts, rate card, conflicts-register extracts
2. Outlook: staffing request and mobilisation emails
3. The firm's resource management or PSA system: bench roster, current allocation, soft bookings
4. The firm's HR system: skills, certifications, seniority, location, languages, approved leave
5. The firm's conflicts and independence register

## Fluent icons

| Item | Fluent icon ID |
|---|---|
| Plugin | `ic_fluent_people_team_24_regular` |
| role-intake | `ic_fluent_document_briefcase_24_regular` |
| bench-query | `ic_fluent_people_search_24_regular` |
| fit-score | `ic_fluent_data_bar_vertical_star_24_regular` |
| constraint-check | `ic_fluent_person_prohibited_24_regular` |
| slate-draft | `ic_fluent_clipboard_text_edit_24_regular` |

## Accent colour

`#3949AB`

## Per-skill compatibility (matches SKILL.md frontmatter)

| Skill | compatibility |
|---|---|
| role-intake | Reads user-supplied files (staffing request email, SOW role extract, rate-card excerpt) with the file-read tool; Python 3 optional to build the JSON payload. No bundled engine and no connectors required. Read-only: never writes to a resource or staffing system. |
| bench-query | Reads user-supplied roster, availability, leave, rate-card and conflicts-register exports (CSV or JSON) with the file-read tool; Python 3 to normalise them into bench.json and constraints.json. No bundled engine and no connectors required. Read-only: never writes to a resource or staffing system. |
| fit-score | Requires Python 3 (standard library only) to run the bundled scripts/fit_score.py and scripts/slate_rank.py on roles.json and bench.json from earlier skills or the user. No connectors required. Writes local JSON only; never writes to a resource or staffing system. |
| constraint-check | Requires Python 3 (standard library only) to run the bundled scripts/constraint_check.py on roles.json from role-intake, bench.json and constraints.json from bench-query, and ranked.json from fit-score. No connectors required. Writes local JSON only; never clears conflicts or writes to a resource, staffing or conflicts system. |
| slate-draft | Requires Python 3 (standard library only) to run the bundled scripts/slate_validate.py on governed.json from constraint-check, re-derived from roles.json, bench.json and constraints.json. No connectors required. Returns the draft in chat or as a document; never sends, posts or writes back to any system. |

## Privacy and terms

- Privacy: https://privacy.microsoft.com/privacystatement
- Terms of use: https://www.microsoft.com/servicesagreement
