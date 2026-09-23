# Fit Scoring Rubric — Engagement Staffing & Bench Match
Deterministic rules consumed by `fit_score.py` and `slate_rank.py`. Engine constants mirror these sections and cite them by section number.

## 1. Component weights
| Rule | Component | Weight |
|---|---|---:|
| 1.1 | Required and preferred skill match, including certifications | 0.40 |
| 1.2 | Seniority alignment | 0.15 |
| 1.3 | Availability and utilisation context | 0.20 |
| 1.4 | Location and language fit | 0.10 |
| 1.5 | Rate-band fit | 0.10 |
| 1.6 | Relevant industry or delivery continuity | 0.05 |

## 2. Skill-match scoring
| Rule | Condition | Score treatment |
|---|---|---|
| 2.1 | Required skill coverage | 70% of the skill component is proportional to required skills matched |
| 2.2 | Preferred skill coverage | 20% of the skill component is proportional to preferred skills matched; no preferred skills means full credit |
| 2.3 | Required certifications | 10% of the skill component is proportional to required certifications matched; no required certifications means full credit |

## 3. Seniority scoring
| Rule | Condition | Score |
|---|---|---:|
| 3.1 | Candidate seniority equals requested seniority | 1.00 |
| 3.2 | Candidate is one band above or below | 0.75 |
| 3.3 | Candidate is two bands away | 0.40 |
| 3.4 | Candidate is more than two bands away | 0.00 |

## 4. Availability and utilisation scoring
| Rule | Condition | Score treatment |
|---|---|---|
| 4.1 | Effective available capacity is `100 - current allocation - approved leave overlap - soft-booked allocation overlap` | Availability component is capped at `effective available capacity / requested allocation` |
| 4.2 | Approved leave and soft-booked pursuits count even when the base resource system allocation is 0% | Count both in effective capacity; do not let a nominally open allocation overstate availability |
| 4.3 | Utilisation after staffing is `current allocation + requested allocation` | Engine records the figure for review; it is not computed in prose |

## 5. Location and language scoring
| Rule | Condition | Score treatment |
|---|---|---|
| 5.1 | Required location match or role marked remote-friendly | 60% of location/language component |
| 5.2 | Required language coverage | 40% of location/language component; no required languages means full credit |

## 6. Rate-band scoring
| Rule | Condition | Score |
|---|---|---:|
| 6.1 | Candidate rate is within role rate band | 1.00 |
| 6.2 | Candidate rate is up to 10% above the role maximum | 0.60 |
| 6.3 | Candidate rate is more than 10% above the role maximum | 0.20 |
| 6.4 | Candidate rate is below the role minimum | 0.90 |

## 7. Ranking and recommendation threshold
| Rule | Condition | Effect |
|---|---|---|
| 7.1 | Provisional ranking | Sort by deterministic fit score descending, then candidate ID ascending as tie-breaker |
| 7.2 | Minimum recommendable score | Eligible candidates below 70.0 are not recommended; the role receives a gap statement if no eligible candidate meets the floor |
| 7.3 | Ranking is pre-governance until `constraint_check` runs | A high fit score never clears independence or availability constraints |
