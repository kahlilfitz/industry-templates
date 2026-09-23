---
name: guideline-check
description: Governs drafted and coded time narratives against client billing guidelines after `code-map`. Use when the user asks "will this narrative get rejected?", "check billing guideline compliance", "catch block billing", "find prohibited terms", "what will pre-bill reject?", or "is this time compliant?" Run before `exception-report`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Delivery Billing Hygiene
---
# Guideline Check (Govern)
## Purpose
Determine narrative compliance against billing guidelines: minimum detail, block billing, prohibited terms, vague wording, required actor/subject/purpose, non-billable activity, increments, duplicate meetings, code mismatch and missing time.
## When to use
After `code-map` in every chain, and directly whenever a user asks whether an entry will be rejected, whether a narrative is compliant, or what is missing from the week.
## Inputs
`coded.json` with drafted narratives, mapped codes, activity signals, guidelines and provenance.
## Steps
1. Run `scripts/guideline_check.py --coded coded.json --out governed.json`.
2. Quote verdicts, flags, missing-time findings and citations verbatim.
3. Do not override a reject, hold or missing-time finding because the prose sounds professional.
4. Send `governed.json` to `exception-report` for the engagement-manager view.
## Output
`governed.json` with entry-level `compliance`, package-level `exception_list`, `missing_time_report`, and `prebill_summary`.
## Grounding requirements
Every flag cites the guideline section that fired and the source activity or timesheet row. Missing-time findings cite the unrecorded activity signal.
## Constraints
- Govern is explicit: the compliance verdict is a determination, not a preference.
- The model never decides compliance and never suppresses a flag.
- Draft-first: the skill does not submit time, approve pre-bills, write off WIP or bill a client.
## Escalation / uncertainty
Confidence below 0.75, unknown code, disabled signals or conflicting evidence must be held for human review by the billing coordinator or engagement manager.
