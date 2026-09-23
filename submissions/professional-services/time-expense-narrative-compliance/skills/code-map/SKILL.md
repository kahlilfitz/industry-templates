---
name: code-map
description: Maps drafted time narratives to the client's phase and task code structure after `narrative-draft`. Use when the user asks "what code should this use?", "map my time to billing codes", "is this task code wrong?", or before checking whether a narrative will be rejected. Run before `guideline-check`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Delivery Billing Hygiene
---
# Code Map
## Purpose
Deterministically map each drafted time entry to the illustrative phase/task code structure and surface submitted-code mismatches with citations.
## When to use
After `narrative-draft`, whenever narratives need task-code mapping or an existing timesheet export needs code hygiene before pre-bill.
## Inputs
`drafted.json` and the controlled task-code structure represented in the contract.
## Steps
1. Run `scripts/code_map.py --drafted drafted.json --out coded.json`.
2. Quote recommended phase/task codes and mismatch flags exactly.
3. Treat a plausible-but-wrong submitted code as a pre-bill exception when the engine flags it.
4. Pass `coded.json` to `guideline-check`.
## Output
`coded.json` with `code_mapping` on each entry: recommended phase/task, submitted-vs-recommended comparison, confidence, source and citations.
## Grounding requirements
Every mapped code cites `task-phase-codes.md`; submitted-code mismatches cite both the code structure and the client guideline section requiring alignment.
## Constraints
- Code mapping is rules-engine-only; the model never substitutes a more convenient code.
- The illustrative code set is synthetic and must be replaced with the firm's controlled taxonomy before production use.
- Draft-first: this skill does not post time or recode the billing system.
## Escalation / uncertainty
Unknown or conflicting activity signals map to `UNMAPPED` and hold for review. Keyword-only inference with a submitted-code disagreement must be escalated.
