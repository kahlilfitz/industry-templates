# Listing metadata - Engagement Mobilization & Onboarding Pack

Draft values for the shared listing template. Not bundled in the package. Plugin version 1.0.6.

## Name

- **name.short:** Engagement Mobilization Pack
- **name.full:** Engagement Mobilization & Onboarding Pack

## Description

**description.short:** Joiner mobilization packs: SOW scope, cleared knowledge, wall and access checks

**description.full** (exactly as in `manifest.json`):

```text
Drafts an internal mobilization and onboarding pack for a Professional Services engagement joiner. Deterministic engines digest SOW scope, separate confirmed from proposed staff, match only released prior knowledge, apply the ethical-wall register and draft least-privilege access requests, with every decision cited. Output is a draft for human review: it does not provision access, grant wall exceptions, assign staff, send messages or approve anything.

Sign up: https://www.microsoft.com/en-us/copilot/pricing/enterprise
Get started: https://support.microsoft.com/en-us/microsoft-365-copilot/get-started-with-cowork
Help: https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/use-cowork
Contact us: https://support.microsoft.com/home/contact
```

## Category and industry

- **Category:** Project management; Workflow & Process Management; Productivity
- **Industry:** Professional Services

## Top 3 prompts

1. Build an onboarding pack for Taylor Reed, who joins the Orchard Ridge Clinics engagement as delivery analyst on Monday, from the SOW, engagement letter, pursuit record and confirmed roster.
2. Mobilize the Nimbus Retail Bank engagement for Riley Chen: check the ethical-wall register and draft the access-request checklist and joiner briefing.
3. Start the onboarding pack for our new joiner: summarise SOW scope and exclusions, match released prior knowledge from closeout and draft the first-week plan for internal review.

## Conversation starters

1. Start the onboarding pack
2. What is in and out of scope for the joiner?
3. Who is confirmed vs proposed?
4. What prior knowledge can the joiner use?
5. Check ethical walls for the joiner
6. What access should we request for the joiner?

## Connectors (priority order)

1. SharePoint / engagement workspace: the SOW, engagement letter, pursuit record and the workspace inventory (read-only).
2. The firm's conflicts / ethical-wall register: the joiner's wall status and briefing topics (read-only; the plugin never grants an exception).
3. The firm's staffing / resource management system: the confirmed roster and the Scenario 02 staffing output (read-only; the plugin never assigns anyone).
4. Microsoft Teams: the engagement team and channels named in the workspace inventory (read-only; the plugin never adds members).
5. Outlook: SOW or engagement-letter extracts and pursuit notes when they arrive by e-mail (read-only; the plugin never sends).

No connector is required: every skill also works on user-supplied files.

## Icons

| Item | Fluent icon ID |
|---|---|
| Plugin | `ic_fluent_rocket_24_regular` |
| `engagement-retrieve` | `ic_fluent_document_search_24_regular` |
| `roster-pull` | `ic_fluent_people_list_24_regular` |
| `knowledge-match` | `ic_fluent_book_search_24_regular` |
| `wall-check` | `ic_fluent_shield_keyhole_24_regular` |
| `pack-draft` | `ic_fluent_notepad_person_24_regular` |

## Accent colour

`#B8431E`

## Per-skill compatibility

| Skill | Compatibility |
|---|---|
| `engagement-retrieve` | Requires Python 3 (standard library only) to run scripts/scope_digest.py. Reads user-supplied files: the SOW, engagement-letter and pursuit-record extracts, the confirmed-roster CSV and the Scenario 02 staffing JSON. No connectors required; writes scope.json only. |
| `roster-pull` | Requires Python 3 (standard library only) to run scripts/verify_render.py, which re-derives scope.json from the user-supplied SOW, letter and pursuit extracts, confirmed-roster CSV and Scenario 02 staffing JSON before the roster is shown. No connectors required; writes no files. |
| `knowledge-match` | Requires Python 3 (standard library only) to run scripts/knowledge_match.py. Reads user-supplied files: scope.json, the raw engagement inputs and staffing JSON, the Scenario 01 Closeout governed JSON and the ethical-wall register CSV. No connectors required; writes matched.json only. |
| `wall-check` | Requires Python 3 (standard library only) to run scripts/wall_check.py and scripts/access_checklist.py. Reads user-supplied files: matched.json or governed.json, the raw engagement inputs, staffing and Closeout JSON, the ethical-wall register and the workspace-inventory CSV. No connectors required; writes governed.json, access-checklist.json and mobilization-pack.md. |
| `pack-draft` | Requires Python 3 (standard library only) to run scripts/verify_render.py, which re-derives access-checklist.json and mobilization-pack.md from the user-supplied raw inputs, staffing and Closeout JSON, wall register and workspace inventory. No connectors required; produces a Markdown draft for review. |

## Privacy and terms

- **Privacy:** https://privacy.microsoft.com/privacystatement
- **Terms of use:** https://www.microsoft.com/servicesagreement
