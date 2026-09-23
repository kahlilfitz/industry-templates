---
name: exception-report
description: Creates the engagement-manager pre-bill exception list after `guideline-check`. Use when the user says "show me the pre-bill exceptions", "what needs fixing before billing?", "summarize rejected narratives", "missing time report", or "send my billing coordinator the cleanup list".
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Delivery Billing Hygiene
---
# Exception Report
## Purpose
Turn governed engine output into a concise review packet: compliant drafts, rejectable narratives, code mismatches, duplicate-meeting issues, non-billable entries and missing-time findings.
## When to use
After `guideline-check`, or when the user asks for the pre-bill exception list, missing-time report, WIP cleanup list or engagement-manager review packet.
## Inputs
`governed.json` from `guideline-check` under contract `ps.time-expense-narrative-compliance.v1`.
## Steps
1. Read `exception_list[]`, `missing_time_report[]` and `prebill_summary` from the governed output.
2. Draft a human-readable exception report grouped by reject, needs-review and missing-time category.
3. Include entry IDs, people, dates, durations, recommended fixes and citations.
4. Preserve the boundary: this is a draft review packet, not an approval or write-off.
## Output
A pre-bill exception report for the engagement manager and billing coordinator, plus cited draft narratives ready for human review.
## Grounding requirements
Every exception must quote the engine flag and citation. Every missing-time item must cite the source activity signal.
## Constraints
- Do not remove, downgrade or reword engine flags into softer conclusions.
- Do not submit time, approve a pre-bill, write off WIP, bill a client or email the client.
- Keep synthetic/demo data separate from production matter data.
## Escalation / uncertainty
Route rejectable entries, low-confidence entries and missing-time findings to the billing coordinator or engagement manager. Policy exceptions remain human decisions.
