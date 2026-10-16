# Listing metadata draft: Engagement Closeout & Knowledge Harvest

Draft for the shared "Skills and Plugin Metadata Template" workbook. Not packaged. Values marked
"exactly as in the manifest" must stay in sync with `manifest.json`.

## Name

- **name.short** (26/30): Closeout Knowledge Harvest
- **name.full** (39/100): Engagement Closeout & Knowledge Harvest

## Description

**description.short** (77/80), exactly as in the manifest:

> Engagement closeout: reusable assets, lessons and sanitised knowledge records

**description.full**, exactly as in the manifest:

```text
Closes out a professional services engagement: assembles deliverables, decision log and retrospective notes, scores reusable assets, clusters lessons, runs a confidentiality gate and drafts a sanitised knowledge record for practice review. Draft-first: it never publishes to a knowledge base, clears a confidentiality restriction, approves external use or waives a client term.

Sign up: https://www.microsoft.com/en-us/copilot/pricing/enterprise
Get started: https://support.microsoft.com/en-us/microsoft-365-copilot/get-started-with-cowork
Help: https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/use-cowork
Contact us: https://support.microsoft.com/home/contact
```

## Category and industry

- **Category:** Content management; Project management; Collaboration
- **Industry:** Professional Services

## Top 3 prompts

Each runs the full chain (artifact-assemble, asset-identify, lesson-cluster, sanitize-check,
knowledge-record).

1. Close out engagement PS-CL-1842: assemble the final deliverables from the engagement SharePoint
   folder, find reusable assets, cluster the lessons learned, sanitise everything and draft the
   knowledge record for practice review.
2. We are wrapping up the grid operations engagement this week. Pull the deliverable register,
   decision log and retrospective notes, tell me what we can reuse and what has to be held for
   confidentiality, and draft the closeout knowledge record.
3. Before the team rolls off, harvest the reusable assets and lessons from this engagement, run the
   confidentiality gate, and prepare a governed knowledge record and credential handoff for review.

## Conversation starters

1. Close out this engagement and draft the knowledge record
2. What can we reuse from this engagement?
3. Is the final deliverable package complete?
4. Cluster the retrospective into lessons learned
5. Can we share this externally? Run the confidentiality gate
6. Prepare the closeout for practice review

## Connectors (priority order)

1. SharePoint (engagement workspace, deliverable register, confidentiality terms extract)
2. OneDrive (engagement artifacts and retrospective notes held by the team)
3. Microsoft Planner (deliverable and status tracking)
4. Microsoft Teams (retrospective meeting transcripts and notes)
5. The firm's project or PSA system of record (deliverable register and status history; read only)

Owner: verify each against the Top 200 connector list.

## Fluent icons

| Item | Fluent icon ID |
|---|---|
| Plugin | `ic_fluent_archive_24_regular` |
| artifact-assemble | `ic_fluent_box_multiple_24_regular` |
| asset-identify | `ic_fluent_box_search_24_regular` |
| lesson-cluster | `ic_fluent_lightbulb_24_regular` |
| sanitize-check | `ic_fluent_shield_lock_24_regular` |
| knowledge-record | `ic_fluent_book_add_24_regular` |

## Accent colour

`#0B6A7A`

## Per-skill compatibility (matches SKILL.md frontmatter)

| Skill | compatibility |
|---|---|
| artifact-assemble | Reads user-supplied closeout files (deliverable register, decision and risk logs, retrospective notes, confidentiality terms) with the file-read tool or an existing SharePoint or OneDrive connection; optionally uses Python 3 to write engagement.json locally. No scripts to run, no write, send or publish connectors. |
| asset-identify | Requires Python 3 (standard library only) to run scripts/asset_identify.py on the engagement.json payload from artifact-assemble; writes asset_shortlist.json locally. No connectors, network access or outbound actions. |
| lesson-cluster | Requires Python 3 (standard library only) to run scripts/lesson_cluster.py on asset_shortlist.json from asset-identify; writes lessons_clustered.json locally. No connectors, network access or outbound actions. |
| sanitize-check | Requires Python 3 (standard library only) to run scripts/sanitize_check.py on lessons_clustered.json from lesson-cluster; writes governed.json locally. No connectors, network access or outbound actions. |
| knowledge-record | Reads governed.json produced by sanitize-check with the file-read tool; no scripts or connectors required. Drafts Markdown in chat or a local document; no email, Teams, SharePoint-write, knowledge-base publishing or credential-creation tools. |

## Privacy and terms

- Privacy: https://privacy.microsoft.com/privacystatement
- Terms of use: https://www.microsoft.com/servicesagreement
- Developer website: https://www.microsoft.com/en-us/copilot/features/cowork
