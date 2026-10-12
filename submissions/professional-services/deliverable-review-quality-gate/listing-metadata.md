# Listing metadata - Deliverable Review & Quality Gate

Draft values for the shared listing template. Not bundled in the package. Plugin version 1.0.5.

## Name

- **name.short:** Deliverable Quality Gate
- **name.full:** Deliverable Review & Quality Gate for Professional Services

## Description

**description.short:** Map deliverable claims to evidence, run quality gates, draft a review packet

**description.full** (exactly as in `manifest.json`):

```text
Checks a client deliverable against your firm's quality-gate criteria. It maps each assertion to supporting evidence, runs the release gates, ranks issues by severity and drafts a partner review packet that cites every finding. Outputs are drafts for a human reviewer: it never signs off, approves client issue, authorizes reliance or sends anything.

Sign up: https://www.microsoft.com/en-us/copilot/pricing/enterprise
Get started: https://support.microsoft.com/en-us/microsoft-365-copilot/get-started-with-cowork
Help: https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/use-cowork
Contact us: https://support.microsoft.com/home/contact
```

## Category and industry

- **Category:** TODO (owner): choose from the guide's category/industry list
- **Industry:** TODO (owner): choose from the guide's category/industry list (current repository industry: Professional Services)

## Top 3 prompts

1. Review the draft benefits report in the engagement workspace against our QRM gate criteria and tell me what blocks client issue.
2. Check every quantified claim in this deliverable against the support pack and draft the partner review packet.
3. Can this deliverable go to the client and the lender? Run the quality gate and rank the release blockers.

## Conversation starters

1. Run the quality gate on this deliverable
2. Which claims in this draft are not substantiated?
3. Which disclaimer does this deliverable need?
4. Did the fixes from the last QRM review land in the document?
5. Draft the partner review packet
6. What needs fixing before client issue?

## Connectors (priority order)

1. SharePoint / engagement workspace: the draft deliverable, support pack and evidence files.
2. OneDrive: draft deliverables and evidence shared by the engagement team.
3. Outlook: the distribution list and prior review notes when they arrive by e-mail (read-only; the plugin never sends).
4. The firm's QRM review tracker: prior review findings and closure status.

Owner: verify each against the Top 200 connector list.

## Icons

| Item | Fluent icon ID |
|---|---|
| Plugin | `ic_fluent_document_checkmark_24_regular` |
| `deliverable-ingest` | `ic_fluent_document_arrow_down_24_regular` |
| `criteria-retrieve` | `ic_fluent_clipboard_task_list_ltr_24_regular` |
| `assertion-map` | `ic_fluent_link_multiple_24_regular` |
| `gate-check` | `ic_fluent_shield_checkmark_24_regular` |
| `review-packet` | `ic_fluent_document_bullet_list_24_regular` |

## Accent colour

`#2E7D32`

## Per-skill compatibility

| Skill | Compatibility |
|---|---|
| `deliverable-ingest` | No scripts of its own. Reads the user-supplied draft deliverable, evidence index, recipient list, registers and prior review notes read-only (for example from an engagement workspace, SharePoint or OneDrive); no connector is required. Produces review-input.json for assertion-map, whose engine needs Python 3. |
| `criteria-retrieve` | No scripts. Reads its bundled references/ and contracts/ plus the user-supplied criteria extract, required-language register and prior-review tracker read-only; no connector is required. |
| `assertion-map` | Requires Python 3 (standard library only) for scripts/assertion_map.py. Reads review-input.json supplied by the user or deliverable-ingest and writes assertion-mapped.json; no network access or connector is required. |
| `gate-check` | Requires Python 3 (standard library only) for scripts/gate_check.py and scripts/severity_rank.py, and for skills/assertion-map/scripts/assertion_map.py when assertion-mapped.json is missing. Reads review-input.json and engine output; no network access or connector is required. |
| `review-packet` | Requires Python 3 (standard library only) to run skills/gate-check/scripts/severity_rank.py --verify. Reads severity-ranked.json and review-input.json and writes a draft markdown packet; no network access or connector is required. |

## Privacy and terms

- **Privacy:** https://privacy.microsoft.com/privacystatement
- **Terms of use:** https://www.microsoft.com/servicesagreement
