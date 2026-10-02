# Severity Rules - Deliverable Review & Quality Gate
Deterministic rules consumed by assertion_map.py, gate_check.py and severity_rank.py. Constants in the engines mirror these sections.

## 1. Severity classes
1.1 `release_blocker`: issue creates firm-risk, client-risk or third-party reliance risk if the deliverable is released as-is. Examples: unsupported headline quantified benefit, wrong reliance language for a third-party recipient, confidentiality breach, or an unsubstantiated conclusion framed as definitive.
1.2 `must_fix`: issue must be corrected before release but does not alone create the same immediate release-risk profile. Examples: missing licensed-content attribution, prior finding marked closed without the fix, required limitation missing near a recommendation.
1.3 `advisory`: quality, clarity or formatting improvement that should be reviewed but does not block partner judgement or release by itself.

## 2. Confidence floors
2.1 Any extraction, mapping or gate confidence below 0.72 is escalated for human confirmation.
2.2 Evidence support below 0.70 is treated as unsupported unless a stricter assertion-class floor applies.
2.3 Quantified claims require evidence support at or above 0.80 and traceable analytical provenance.

## 3. Ranking and downgrade controls
3.1 A release blocker can never be auto-downgraded by the model, by narrative polish, by schedule pressure or by the existence of a disclaimer.
3.2 Findings rank first by severity, then by confidence, then by page and paragraph so a reviewing partner starts with the highest-risk issue. `location.page` and `location.paragraph` must be integers or null; null (a register-level finding with no page) ranks after page-located findings of the same severity and confidence. Printed page labels such as roman numerals belong in `location.label`; any other page or paragraph value is a clean input error, never a guessed order.
3.3 The review-status verdict is `not_ready_for_release` if any release blocker exists, `partner_review_required_must_fix` if must-fix items exist without blockers, `partner_review_required_advisories_only` when only advisories remain and `partner_review_required_no_engine_findings` only when no findings and no escalations exist. An escalation is a hold: escalations with no finding give `not_ready_for_release`. `findings` and `escalations` are required arrays; an absent or non-array value is a clean input error, never an empty run.
3.4 One finding is kept per `finding_id`. When findings share an ID, the one with the highest severity is kept (the first on a tie), so a duplicate is never counted twice and never lowers severity, and the collapse is escalated for confirmation.

## 4. Human judgement boundary
4.1 The engine can block or flag; only the reviewing partner or authorized QRM role can clear the gate.
4.2 The review packet must state that it does not approve release, sign off the deliverable, clear the quality gate or substitute for professional judgement.
