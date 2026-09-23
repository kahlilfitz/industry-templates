---
name: clause-select
description: Runs deterministic `clause_select.py` after `scope-extract` to select approved clause-library language for the SOW and stop if the approved library is absent or unversioned. Use when the user says "use approved clauses", "which clauses belong in this SOW?", "draft the SOW from our clause library", or after `scope-extract` produces `scope.json`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Pursuit Contracting
---
# Clause Select
## Purpose
Select the firm's approved clause language by library ID and version, with thin-input blocks carried forward so unsupported commitments are not drafted.
## When to use
After `scope-extract` and before `deviation-flag`.
## Inputs
- `scope.json` under contract `ps.sow-drafting-scoping-notes.v1`.
- Versioned approved clause library JSON from `notes-ingest`.
## Steps
1. Verify the clause library is present, versioned and marked `approved`.
2. If the library is missing, stale or unversioned, stop and return degraded mode: structured extraction only, no Govern step and no approved-language drafting.
3. Run `scripts/clause_select.py --scope scope.json --library approved-clause-library.json --out selected-clauses.json`.
4. Quote the selected `library_id`, `library_version`, approved clause and risk tier exactly.
5. Mark clauses tied to blocked commitments as `thin_input_blocked`; do not draft their commitment prose.
## Output
`selected-clauses.json` with `selected_clauses[]` carrying library ID, version, risk tier, approved clause text, draft allowance and deviation state.
## Grounding requirements
Every clause cites `approved-clause-library.md` and the retrieved library version. The prior SOW is never a source of approved language.
## Constraints
- If the clause library is absent or unversioned, say so and stop. Do not invent approved language.
- Clause selection is deterministic; the model never swaps in another clause because it sounds better.
- Thin-input blocks from `scope-extract` must remain blocks.
## Escalation / uncertainty
Missing or uncontrolled library: deploy only extraction/thin-input reporting until a maintained approved clause library exists.
