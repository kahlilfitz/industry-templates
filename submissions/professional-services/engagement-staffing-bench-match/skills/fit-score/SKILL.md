---
name: fit-score
description: Computes deterministic fit scores, utilisation context and provisional ranks using fit_score and slate_rank. Use when the user says "rank the bench", "build me a slate", "score the candidates", "who is the best fit?", after bench-query and before constraint-check.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Fit Score
## Purpose
Apply `references/fit-scoring-rubric.md` deterministically: component scores, total fit score, effective available capacity, utilisation after staffing and provisional rank for every candidate-role pair.
## When to use
After `bench-query` and before `constraint-check` in every staffing run.
## Inputs
`roles.json` + `bench.json` using contract `ps.engagement-staffing-bench-match.v1`.
## Steps
1. Validate that every role and candidate carries `source`, `confidence` and `citation`.
2. Run `scripts/fit_score.py --roles roles.json --bench bench.json --out scored.json`.
3. Run `scripts/slate_rank.py --scored scored.json --out ranked.json`.
4. Quote scores, components, utilisation and provisional rank verbatim. The model may explain the meaning but never recomputes a number.
5. Hand off `ranked.json` to `constraint-check`.
## Output
`scored.json` and `ranked.json`, including `scored_roles[]`, `ranked_roles[]`, component scores and utilisation context.
## Grounding requirements
Every score cites the rubric sections used. Every utilisation figure cites the candidate availability record.
## Constraints
- Ranking here is pre-governance. A high score never clears independence, ethical-wall, prior-role or availability constraints (`fit-scoring-rubric.md #7.3`).
- Do not remove low-scoring or apparently conflicted candidates before Govern.
## Escalation / uncertainty
If role or candidate confidence is below 0.75, pass the candidate through with the confidence visible and flag it for `constraint-check` under `independence-eligibility-rules.md #8.1`.
