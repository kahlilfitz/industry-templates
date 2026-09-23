---
name: party-intake
description: Starts a conflicts and independence pre-check from a pursuit record, intake form or email. Use when the user says "run a conflicts check", "can we take this work?", "start independence pre-check", "new pursuit risk review", "check this client and party list", before entity-resolve.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Risk and Compliance
---
# Party Intake
## Purpose
Turn the raw pursuit intake into the `ps.conflicts-independence-precheck.v1` contract: prospective client, matter description, requested services, jurisdictions, adverse parties, counterparties, beneficial owners and named individuals.
## When to use
At the start of every conflicts and independence pre-check.
## Inputs
- Pursuit record, intake form or email.
- Prospective client name and known aliases.
- Matter type, requested services, jurisdictions and target/party list.
- Any partner assumptions or urgency notes as context only.
## Steps
1. Extract structured `prospective_client`, `matter` and `parties[]` with `source=skill:party-intake`, confidence and citations.
2. Preserve the user's original wording; do not normalize names beyond obvious whitespace cleanup.
3. Flag missing required fields in `escalations[]` rather than filling them from assumptions.
4. Write `intake.json` under the shared contract for `entity-resolve`.
## Output
`intake.json` containing the first hop of the contract.
## Grounding requirements
Every party and service line cites the intake source and carries confidence. Partner pressure, deadlines and commercial context must be captured as notes, never as decision inputs.
## Constraints
- No conflict classification happens here.
- Do not say the matter is clear, acceptable or approved.
- Do not drop parties just because they are described as "minor", "different entity" or "only a brand".
## Escalation / uncertainty
Missing party roles, unclear requested services, incomplete jurisdictions or uncertain client identity must be carried forward as review flags.
