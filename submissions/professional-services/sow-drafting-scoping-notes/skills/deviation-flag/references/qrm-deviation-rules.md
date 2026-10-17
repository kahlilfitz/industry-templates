# QRM Deviation Rules - SOW Drafting from Scoping Notes

Deterministic rules consumed by `scope_extract.py`, `clause_select.py` and `deviation_flag.py`.
Constants in the engines mirror these sections.

## 1. Review ownership
| Rule | Condition | Effect |
|---|---|---|
| 1.1 | A deviation changes risk allocation, remedies, acceptance, payment timing or client obligations. | The deviation is a governance item, not drafting style; route for review before the SOW is issued. |
| 1.2 | A prior SOW contains a QRM-approved one-off concession. | The concession is not portable to a new client, new pursuit or new SOW unless re-approved. |

## 2. Clause family sensitivity
| Rule | Family | Sensitivity |
|---|---|---|
| 2.1 | limitation_of_liability | High sensitivity. Broader liability caps, indirect-damage exposure, uncapped carve-outs or client-favourable remedy expansions require QRM and legal review. |
| 2.2 | acceptance | Medium sensitivity. Missing objective criteria or deemed acceptance without criteria blocks drafting until scoping resolves the criteria. |
| 2.3 | ip_ownership | Medium sensitivity. Assignment of pre-existing IP or accelerators requires legal review. |
| 2.4 | payment_terms | Medium sensitivity. Extended payment terms, holdbacks or success-contingent payment require partner and finance review. |
| 2.5 | termination | Medium sensitivity. Termination for convenience without payment for work performed requires partner and legal review. |
| 2.6 | warranty_disclaimer | Medium sensitivity. Expanded warranties beyond professional services standard require legal review. |
| 2.7 | change_control | Low sensitivity. Removing written change-control mechanics requires partner review. |
| 2.8 | data_protection | High sensitivity. Uncapped data-protection indemnity or security remedies outside the approved framework require QRM and legal review. |

## 3. Deviation severity and routing
| Rule | Condition | Severity | Required route |
|---|---|---|---|
| 3.1 | High-sensitivity family with broader client remedy, uncapped exposure or non-portable one-off approval. | critical | QRM + legal + engagement partner |
| 3.2 | Medium-sensitivity family with commercial or delivery-risk change. | major | Engagement partner + QRM |
| 3.3 | Prior SOW clause is marked one-off, client-specific or non-portable. | critical | QRM + legal; quote approved library clause beside inherited clause |
| 3.4 | Minor drafting difference that does not change risk allocation. | minor | Contract manager review |

## 4. Thin-input refusal rules
| Rule | Condition | Effect |
|---|---|---|
| 4.1 | Evidence confidence for a commitment is below 0.72 (`THIN_INPUT_CONFIDENCE_FLOOR`). | Do not draft the commitment; add it to the thin-input report. |
| 4.2 | Acceptance criteria, data ownership, client obligations, milestone basis or dependency owner is missing. | Convert the gap into an assumption and exclusion; do not invent the missing fact. |
| 4.3 | A go-live date is verbal, aspirational or lacks plan evidence. | Treat it as a planning target only; do not draft it as a committed delivery date. |
| 4.4 | A blocked commitment is tied to a clause family. | Select the approved clause for review if the library exists, but mark the clause `thin_input_blocked` and withhold commitment prose. |
