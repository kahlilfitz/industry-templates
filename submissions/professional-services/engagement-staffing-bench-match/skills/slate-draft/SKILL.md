---
name: slate-draft
description: Drafts the partner-ready staffing recommendation after constraint-check, including ranked eligible slate, refused top matches, conflicts, utilisation context and gap statements. Use when the user says "draft the recommendation", "build me a slate", "send partner approval", or after constraint-check.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Mobilisation
---
# Slate Draft
## Purpose
Create the terminal draft: a staffing recommendation record for partner approval, populated only from `governed.json`.
## When to use
After `constraint-check`, when the user asks for a slate, recommendation, partner approval note or staffing summary.
## Inputs
`governed.json` using contract `ps.engagement-staffing-bench-match.v1`.
## Steps
1. Lead with any Govern refusals, especially if the top provisional candidate was disqualified.
2. For each role, list final eligible candidates in engine order with fit score, component highlights, availability, utilisation after staffing, rate-band context and citations.
3. Include ineligible and needs-review candidates in a separate "not recommended" section with blocking rule and citation.
4. Write the gap statement verbatim for any role with no eligible candidate above the recommendable score floor.
5. Mark the output DRAFT - pending partner approval and independence/resource-management review.
## Output
A drafted staffing recommendation in markdown or the requested document format.
## Grounding requirements
Every score, rank, verdict, utilisation figure and gap statement comes from `governed.json`. Cite role records, bench records and rule sections.
## Constraints
- Draft-first: do not assign people, commit allocations, clear independence flags, change rates or write back to the resource system.
- Do not recommend a candidate marked `ineligible` or `needs_review`.
- Do not invent a "better" slate outside the governed payload.
## Escalation / uncertainty
If there is no eligible candidate above the score floor, state the gap and route to recruiting, subcontractor search, start-date negotiation or scope adjustment; do not pad the slate.
