# Approved Clause Library - SOW Drafting from Scoping Notes

Illustrative summaries only. Replace this file with the firm's controlled, versioned clause
library before production use. Engines cite these sections and never invent approved language.

## 1. Library control
| Rule | Requirement | Effect |
|---|---|---|
| 1.1 | The approved clause library must be present, versioned and marked `approved`. | Without a maintained library, `clause_select.py` stops and returns degraded mode: extraction only, no Govern step. |
| 1.2 | Clause text is selected by library ID and version. | Drafts may quote approved language only from the library payload. Prior SOW language is evidence for deviation detection, not a clause source. |

## 2. Approved clause set
| Section | Library ID | Family | Risk tier | Illustrative approved language summary |
|---|---|---|---|---|
| 2.1 | PS-LOL-001 | limitation_of_liability | high | Mutual aggregate liability is capped at fees paid or payable under the SOW; indirect, consequential and special damages are excluded except where the MSA expressly says otherwise. |
| 2.2 | PS-ACC-001 | acceptance | medium | Deliverables are accepted against written acceptance criteria; the client has five business days to reject with specific defects; silence after the review period is deemed acceptance only where the SOW defines objective criteria. |
| 2.3 | PS-IP-001 | ip_ownership | medium | Pre-existing materials, accelerators and know-how remain provider property; client receives a license to use deliverables for its internal business purposes after payment. |
| 2.4 | PS-PAY-001 | payment_terms | medium | Fees are billed by milestone or monthly in arrears as stated in the SOW; undisputed invoices are due net 30; taxes and reimbursable expenses are excluded unless listed. |
| 2.5 | PS-TERM-001 | termination | medium | Either party may terminate for uncured material breach after notice and cure period; client pays for services performed and approved non-cancellable commitments through the effective date. |
| 2.6 | PS-WAR-001 | warranty_disclaimer | medium | Services will be performed in a professional and workmanlike manner; except for express SOW warranties, all other warranties are disclaimed to the extent permitted. |
| 2.7 | PS-CC-001 | change_control | low | Changes to scope, timing, dependencies, assumptions or fees require a written change order signed by authorized representatives before work proceeds. |
| 2.8 | PS-DP-001 | data_protection | high | Each party follows the data protection addendum and agreed security schedule; data-related remedies and indemnities remain subject to the MSA/SOW liability framework unless QRM approves otherwise. |

## 3. Clause selection rules
| Rule | Condition | Clause family |
|---|---|---|
| 3.1 | Any SOW draft must include limitation of liability, IP ownership, payment, termination, warranty/disclaimer and change control. | PS-LOL-001, PS-IP-001, PS-PAY-001, PS-TERM-001, PS-WAR-001, PS-CC-001 |
| 3.2 | If deliverables or review steps are drafted, include acceptance. | PS-ACC-001 |
| 3.3 | If client data, personal data, test data, protected data or data migration appears in scope, include data protection. | PS-DP-001 |
