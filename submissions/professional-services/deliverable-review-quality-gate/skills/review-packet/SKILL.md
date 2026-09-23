---
name: review-packet
description: Drafts the partner review packet from deterministic `gate-check` and `severity_rank` output. Use when the user says "draft the review packet", "summarize what the partner needs to review", "make the issue list", "what needs fixing before client release?", or after `gate-check` completes.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Quality assurance
---
# Review Packet
## Purpose
Create the terminal artifact: a draft partner review packet ordered by severity, with gate checklist results, unsupported assertions, missing required language, confidentiality/brand findings and prior-review closure status.
## When to use
After `gate-check`, or whenever the reviewer asks for the issue list or review packet.
## Inputs
`severity-ranked.json` under contract `ps.deliverable-review-quality-gate.v1`.
## Steps
1. Validate the payload and lead with `release_readiness.status`.
2. Populate `templates/review-packet-template.md` from contract data only.
3. Order findings exactly as `ranked_findings[]` provides them.
4. Mark the artifact DRAFT and state that only the reviewing partner or QRM can clear the gate.
## Output
`REVIEW-PACKET-<deliverable_id>.md` or equivalent markdown content for human review.
## Grounding requirements
Every issue in the packet must carry gate ID, severity, location, criteria section and citation. Assertions quote the evidence mapping rather than re-evaluating support.
## Constraints
- Draft-first: no sign-off, release approval, client send, system write-back or gate clearance.
- The model writes the narrative but cannot alter engine severities or readiness status.
- Nothing appears in the packet that is not in the contract payload.
## Escalation / uncertainty
If ranked findings include a release blocker, the packet must say `not_ready_for_release` and route to the reviewing partner/QRM owner.
