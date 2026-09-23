# Independence & Eligibility Rules — Engagement Staffing & Bench Match
Illustrative summaries for demo grounding. They are not reproduced standards or a real firm's policy. Deterministic rules consumed by `constraint_check.py`; engine constants mirror these sections.

## 1. Determination discipline
| Rule | Condition | Effect |
|---|---|---|
| 1.1 | Every candidate-role pair receives `eligible`, `ineligible` or `needs_review` | The model quotes the engine verdict and never substitutes its own |
| 1.2 | Any ineligible verdict is a refusal for that role | The candidate cannot be recommended, assigned or manually cleared by the model |

## 2. Cooling-off period for prior client roles
| Rule | Condition | Effect |
|---|---|---|
| 2.1 | Candidate was an employee, officer or board member of the client within 365 days before the role start date | Ineligible for the engagement role |
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
| 6.1 | Effective available capacity is below requested allocation after approved leave and soft-booked pursuits are counted | Ineligible for that role's requested start and allocation |
| 6.2 | Effective capacity is within 10 percentage points of requested allocation | Needs review by the resource manager before recommendation |

## 7. Refusal and gap handling
| Rule | Condition | Effect |
|---|---|---|
| 7.1 | The top provisional candidate is ineligible | The Govern step must state that it refuses the obvious pick and cite the blocking rule |
| 7.2 | No eligible candidate meets the minimum recommendable score | Produce a gap statement rather than padding the slate |

## 8. Confidence floor
| Rule | Condition | Effect |
|---|---|---|
| 8.1 | Extraction or rules confidence is below 0.75 | Hold for human review; do not recommend as cleared |
