---
name: lesson-cluster
description: Clusters decisions and retrospective inputs into lesson themes with the deterministic lesson_cluster engine. Use after asset-identify when the user says "lessons learned", "cluster the retrospective", "what did we learn?", or "write the closeout lessons".
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Lesson Cluster
## Purpose
Apply `references/lesson-taxonomy.md` deterministically so lessons are grouped, ranked and cited before prose is drafted.
## When to use
After `asset-identify`, before `sanitize-check`, for every closeout knowledge harvest.
## Inputs
`asset_shortlist.json` with decision_log and retrospective_inputs carried from `artifact-assemble`.
## Steps
1. Run `scripts/lesson_cluster.py --input asset_shortlist.json --out lessons_clustered.json`.
2. Quote cluster ids, categories, priority scores, evidence ids and citations verbatim.
3. Do not polish any lesson that `sanitize-check` later flags for personal data or confidentiality.
4. Pass named-person and blame signals through to the Govern step.
## Output
`lessons_clustered.json` with `lesson_clusters[]`, evidence citations, sensitivity signals and provenance.
## Grounding requirements
Every lesson cluster cites the decision or retrospective inputs that produced it and the taxonomy section applied.
## Constraints
- The model may draft lesson prose later, but it never invents a cluster or priority.
- Named-person blame is not rewritten here; it is flagged and governed by `sanitize-check`.
- Low-confidence clusters remain review candidates.
## Escalation / uncertainty
Clusters below 0.70 confidence are marked for review rather than presented as final lessons.
