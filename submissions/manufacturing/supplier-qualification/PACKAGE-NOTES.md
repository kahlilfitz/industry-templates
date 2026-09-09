# Supplier Qualification - Cowork Plugin (Wave 2)
Research Assistant (Connect -> Analyze -> Create) · attended, draft-first.
Skills: dossier-ingest -> risk-score -> avl-compare -> qualification-memo.
Contract: mfg.supplier-qualification.v1. Engines: risk_score (#1 cert validity, #2 financial floors, #3 concentration, #4 PPAP), avl_match (#5 recommendation bands). Constants mirror references/qualification-rules.md.
Demos: scenario-a-happy (clean regional-diversifying candidate -> qualify), scenario-b-drama (glossy dossier, premier pricing - but the ISO cert EXPIRED 2 months ago, quick ratio 0.72 declining, same-region concentration, control plan missing from PPAP -> do_not_qualify with named conditions).
Grounded in PPAP, APQP, ISO 9001, IATF 16949. Boundary: memo for approval; awards and AVL changes are human work.
