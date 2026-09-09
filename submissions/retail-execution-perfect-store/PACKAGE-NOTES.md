# Retail Execution & Perfect Store - Cowork Plugin (CPG Wave 2)
Intake & Triage with ranking (Connect -> Analyze -> Create -> Act) · attended, draft-first. The signature CPG field workflow; no retailer-side equivalent.
Skills: visit-prep -> standard-retrieve -> gap-score -> action-register -> visit-report.
Contract: rtl.retail-execution-perfect-store.v1. Engines: visit_score (#1 deterministic pass/fail, photos evidence-only #3.1), gap_rank (#2 value ranking, promo 2x, par-based suggested order #4.1). Constants mirror references/execution-standards.md; standards live in config/ per channel:cluster.
Demos: scenario-a-baseline (solid outlet, two tail gaps), scenario-b-escalation ("92% compliant, quick visit" - the two fails are the hero SKU OOS and the promo display down DURING the promo; value ranking makes the high-scoring store the urgent one).
Upgrade path: shelf-image recognition is Wave 3; this version deliberately avoids the hardware/model dependency.
