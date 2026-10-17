# Scope Classification Rules - Change Order & Scope Control

Deterministic rules consumed by `scope_match.py` and `scope_classify.py`. Engines cite these section numbers; constants in the engines mirror this document.

## 1. Controlling-document hierarchy
| Rule | Condition | Effect |
|---|---|---|
| 1.1 | The SOW contains a numbered clause on scope, deliverables, assumptions or exclusions | The SOW is the controlling document for scope classification. Every classification cites the governing clause quote. |
| 1.2 | The MSA describes change-control mechanics but does not define the work | Use the MSA only to support the change-control route after the SOW determines scope. |

## 2. Out-of-scope precedence
| Rule | Condition | Effect |
|---|---|---|
| 2.1 | A request matches an explicit SOW exclusion | Classify OUT_OF_SCOPE unless rule #4.2 identifies a direct contradiction in the SOW itself. Explicit exclusion beats implied inclusion. |
| 2.2 | A request is caused by a failed SOW assumption | Classify OUT_OF_SCOPE and cite both the failed assumption and the change-control clause. |
| 2.3 | A request is not listed in the closed deliverable list and is not materially similar to a listed deliverable | Classify OUT_OF_SCOPE under deliverable-list closure. |

## 3. In-scope protection
| Rule | Condition | Effect |
|---|---|---|
| 3.1 | A request is materially similar to a listed deliverable and no explicit exclusion applies | Classify IN_SCOPE. The material similarity floor is 0.82 (`MATERIAL_SIMILARITY_FLOOR`). |
| 3.2 | A broad deliverable clause covers the requested form, audience or summary level | Classify IN_SCOPE when the request stays within that deliverable's stated purpose and the similarity floor is met. |

## 4. Ambiguity and refusal
| Rule | Condition | Effect |
|---|---|---|
| 4.1 | Engine confidence is below 0.75 (`CONFIDENCE_FLOOR`) | Classify AMBIGUOUS. The engine refuses to decide and routes to human review. |
| 4.2 | The SOW deliverable list and exclusion list directly contradict each other for the same request | Classify AMBIGUOUS even if one clause appears favorable. Cite both clauses and route to the engagement partner or contract manager. |
| 4.3 | A request lacks a cited SOW clause, estimate basis or source provenance | Classify AMBIGUOUS until the missing evidence is supplied. |
