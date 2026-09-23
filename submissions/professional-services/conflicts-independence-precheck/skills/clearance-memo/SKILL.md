---
name: clearance-memo
description: Drafts a proposed conflicts clearance memo or escalation packet after conflict-classify. Use when the user says "draft the clearance memo", "write the conflicts memo", "prepare the QRM escalation", "can we take this work?", only after classified.json exists.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Risk and Compliance
---
# Clearance Memo
## Purpose
Produce the terminal artifact: a proposed memo for human review or an escalation packet, populated only from `classified.json`.
## When to use
After `conflict-classify`.
## Inputs
`classified.json` under contract `ps.conflicts-independence-precheck.v1`.
## Steps
1. Validate the payload and read `precheck_position`, `conflict_hits[]`, `search_scope` and `escalations[]`.
2. Fill `templates/clearance-memo-template.md`.
3. Lead with the boundary statement: proposed position only, human QRM clearance required.
4. If the position is clean, use exactly the scoped language: "no hits found in the registers searched, subject to review." Do not write "cleared", "approved" or "no conflict".
5. If the position escalates, draft an escalation packet with hit table, rule citations, consent/wall posture and unresolved questions.
## Output
`proposed-clearance-memo.md` or `qrm-escalation-packet.md`.
## Grounding requirements
Every statement about a hit must cite the register row and governing rule from the engine output. The memo must state registers searched, date range, variants tried and unresolved parties.
## Constraints
- Draft-first: nothing is filed, sent, approved or written back.
- The model never changes `precheck_position`, drops hits or downgrades a non-waivable category.
- No output may imply the firm has accepted the engagement.
## Escalation / uncertainty
Any `escalations[]` entry appears above the proposed position and blocks clean memo framing.
