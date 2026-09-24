---
name: narrative-draft
description: Drafts or normalizes time-entry narrative prose from cited activity signals after `activity-pull`. Use when the user says "write up my time", "draft my time entries", "turn my calendar into narratives", or "make these entries client-ready". Run before `code-map`; the model may improve prose, but deterministic output and provenance stay fixed.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: writing
---
# Narrative Draft
## Purpose
Create client-facing narrative drafts from engagement activity while preserving every linked signal, citation and confidence score. The model may write readable prose; compliance is not decided here.
## When to use
After `activity-pull` and before `code-map`, especially for "write up my time", "draft narratives from my week", or "turn these activity signals into time entries".
## Inputs
`activity.json` / normalized activity packet and existing `time_entries[]` in contract `ps.time-expense-narrative-compliance.v1`.
## Steps
1. Validate that the packet uses the expected contract version.
2. Run `scripts/narrative_draft.py --activity activity.json --out drafted.json` for deterministic demo output.
3. If prose is rewritten by the model, preserve the engine's linked `activity_ids`, confidence, source and citations.
4. Do not remove vague terms or compliance issues manually; leave `guideline-check` to flag them.
5. Pass `drafted.json` to `code-map`.
## Output
`drafted.json` with each time entry carrying `draft.narrative`, linked activity evidence, confidence, provenance and citations.
## Grounding requirements
Narrative content must be grounded in activity signals, prior accepted narratives or controlled billing terms. No invented work, attendees, deliverables or client purpose.
## Constraints
- The model drafts prose only; it never decides compliance, code mapping or missing-time flags.
- Existing user-entered narratives are preserved so the Govern step can evaluate what would reach pre-bill.
- Draft-first: no submission, approval, write-off or billing.
## Escalation / uncertainty
If activity evidence is incomplete or ambiguous, keep the entry draftable only as `needs_review` context and cite the missing signal rather than inventing detail.
