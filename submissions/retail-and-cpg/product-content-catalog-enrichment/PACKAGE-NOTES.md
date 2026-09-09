# Product Content & Catalog Enrichment - Cowork Plugin (Retail Wave 1, CPG-enabled)
Doc Extractor & Summarizer (Connect -> Analyze -> Govern -> Create) · attended, draft-first. Both sides of the GDSN feed use it.
Skills: source-ingest -> attribute-normalize -> gap-score -> claim-check (Govern) -> content-draft.
Contract: rtl.product-content-enrichment.v1. Engines: attribute_normalize (GS1 check digit #1.1, taxonomy-only mapping #2.1), completeness_score (#3.1), claim_check (#4 claims + regulated terms). Constants mirror references/enrichment-rules.md; taxonomy map and claim library live in config/.
Demos: scenario-a-baseline (clean normalise, one missing field), scenario-b-escalation (punchy supplier copy - "kills 99.9% of germs", "biodegradable" - blocked without substantiation; one GTIN fails the GS1 check digit; the safe draft uses approved claims only).
Boundary: approval-ready draft records; no channel publish, no claim approval, no taxonomy changes.
