# Independence & Eligibility Rules — Engagement Staffing & Bench Match
Illustrative summaries for demo grounding. They are not reproduced standards or a real firm's policy. Deterministic rules consumed by `constraint_check.py`; engine constants mirror these sections.

## 1. Determination discipline
| Rule | Condition | Effect |
|---|---|---|
| 1.1 | Every candidate-role pair receives `eligible`, `ineligible` or `needs_review` | The model quotes the engine verdict and never substitutes its own |
| 1.2 | Any `ineligible` or `needs_review` verdict is not recommendable for that role | `ineligible` is a refusal; `needs_review` is withheld pending authorized human review. Neither can be assigned or manually cleared by the model |

## 2. Cooling-off period for prior client roles
| Rule | Condition | Effect |
|---|---|---|
| 2.1 | Candidate was an employee, officer, director or board member of the client within 365 days before the role start date | Ineligible for the engagement role; normalize `director`, `board member` and `board-member` as governance roles |
| 2.2 | Candidate held a non-governance client role ending 366-730 days before the role start date | Needs independence review before recommendation |

## 3. Financial-interest restrictions
| Rule | Condition | Effect |
|---|---|---|
| 3.1 | Candidate has an unresolved material financial interest in the client or controlled affiliate | Ineligible until the interest is resolved and cleared |
| 3.2 | Candidate divested a material interest within 30 days of the role start date | Needs independence review; do not recommend as cleared |

## 4. Ethical walls and adverse-party restrictions
| Rule | Condition | Effect |
|---|---|---|
| 4.1 | Candidate is on the wrong side of an active ethical wall involving the client or a live adverse matter | Ineligible for the engagement role |
| 4.2 | Candidate supported a materially adverse matter involving the client within 180 days | Needs independence review |

## 5. Prior assurance or regulated-role restrictions
| Rule | Condition | Effect |
|---|---|---|
| 5.1 | Candidate performed an assurance, audit or regulatory-review role over the same client process within 730 days | Ineligible for transformation, remediation or operating roles over that process |
| 5.2 | Prior role scope is ambiguous | Needs independence review; the model must not infer clearance |

## 6. Availability eligibility
| Rule | Condition | Effect |
|---|---|---|
| 6.1 | Effective available capacity is more than 10 percentage points below requested allocation after time-weighted approved leave and soft-booked pursuits across the role duration are counted | Ineligible for that role's requested start and allocation |
| 6.2 | Effective available capacity is below requested allocation by 10 percentage points or fewer | Needs review by the resource manager before recommendation |
| 6.3 | Role duration or an availability-block boundary is missing or invalid | Use the documented conservative assumption, record an escalation and hold for resource-manager review |

## 7. Refusal and gap handling
| Rule | Condition | Effect |
|---|---|---|
| 7.1 | The top provisional candidate is ineligible | The Govern step must state that it refuses the obvious pick and cite the blocking rule |
| 7.2 | No eligible candidate meets the minimum recommendable score | Produce a gap statement rather than padding the slate |

## 8. Confidence floor
| Rule | Condition | Effect |
|---|---|---|
| 8.1 | Extraction or rules confidence is below 0.75 | Hold for human review; do not recommend as cleared |

## 9. Fail-closed conflict handling
| Rule | Condition | Effect |
|---|---|---|
| 9.1 | A conflict record type, status, materiality, scope or required date is missing or unrecognised | Needs independence review; never infer clearance |
| 9.2 | A conflict names the client, a declared parent, subsidiary or affiliate, including punctuation or corporate-suffix variants | Match normalized whole words; never use raw substring matching. If either entity normalizes to empty, hold for review |
| 9.3 | A financial-interest status is anything other than `divested`, `resolved` or `cleared` | Treat it as unresolved; material interests are ineligible and blank materiality needs review |
| 9.4 | A candidate has no conflicts-register row | Needs independence review; absence of a record is not evidence of clearance |
| 9.5 | Candidate IDs differ only by case, surrounding or repeated whitespace, Unicode compatibility form, invisible format characters or the separators `-`, `_` and `.`, or a register row names an unknown candidate | Match known IDs in one canonical form: NFKC, invisible format characters removed, case-folded, whitespace collapsed, and `-`, `_` and `.` folded. Escalate unknown or blank IDs for mapping review |
| 9.6 | A bench, score or conflict record carries instruction-like, oversize or already-redacted (`[FLAGGED: ...]`) text | Needs review; the candidate is never recommended until the source record is cleaned, and the flagged text is never repeated |
| 9.7 | An ID or name is blank, null, the wrong type, duplicated after canonical folding, or uses a reserved label form (for example `<unknown>` or a redaction marker) | Input error or review hold; never matched, cleared or recommended |
| 9.8 | An intermediate file (`ranked.json`, `governed.json`) does not re-derive exactly from `roles.json`, `bench.json` and `constraints.json` | Refuse with no output; re-run the upstream skills |
| 9.9 | A register row for another client is malformed, or names another client | Validate before scoping; foreign rows are reported only by position and fixed label, never by client name or citation |
| 9.10 | `constraints.json` names a different client or engagement ID than the ranked (role-intake) engagement, or a role start date that differs from it | Refuse with no output; the role-intake engagement is authoritative and the conflicts register may only add declared affiliates |
