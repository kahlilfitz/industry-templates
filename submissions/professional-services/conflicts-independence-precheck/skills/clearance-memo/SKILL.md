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
1. Validate the payload and read `precheck_position`, `conflict_hits[]`, `prior_clearance_context[]`, `search_scope` and `escalations[]`.
2. Fill `templates/clearance-memo-template.md`.
3. Lead with the boundary statement: proposed position only, human QRM clearance required.
4. If the position is clean, use exactly the scoped language: "no hits found in the registers searched, subject to review." Do not write "cleared", "approved" or "no conflict".
5. State `search_scope.registers_searched` verbatim. If `search_scope.registers_not_searched` is non-empty, say so in the memo's opening and frame the result as an incomplete search, never a clean one.
6. If the position escalates, draft an escalation packet with hit table, rule citations, consent/wall posture and unresolved questions.
7. Report `prior_clearance_context[]` as background only, labelled non-controlling.
## Output
`proposed-clearance-memo.md` or `qrm-escalation-packet.md`.
## Grounding requirements
Every statement about a hit must cite the register row and governing rule from the engine output. The memo must state the registers actually searched, any supplied register that was not searched, the date range, variants tried and unresolved parties.
## Constraints
- Draft-first: nothing is filed, sent, approved or written back.
- The model never changes `precheck_position`, drops hits or downgrades a non-waivable category.
- Never assert coverage the engine did not report; the scope paragraph is copied from `search_scope`, not summarised from the inputs.
- A prior clearance decision is never a reason to soften or omit a current hit.
- No output may imply the firm has accepted the engagement.
## Escalation / uncertainty
Any `escalations[]` entry or non-empty `registers_not_searched` appears above the proposed position and blocks clean memo framing.
