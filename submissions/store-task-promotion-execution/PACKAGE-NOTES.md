# Store Task & Promotion Execution - Cowork Plugin (Retail Wave 1)
Doc Extractor & Summarizer with orchestration (Connect -> Analyze -> Create -> Act) · attended, draft-first.
Skills: pack-ingest -> store-map -> readiness-check -> exception-raise -> brief-draft.
Contract: rtl.store-task-promotion-execution.v1. Engines: readiness_check (#1 applicability, #2 completeness, #3 price integrity, #4 fixture conflicts), exception_rank (#5 revenue-impact ranking). Constants mirror references/execution-rules.md.
Config seam: store clusters/formats, price tolerances and velocity extracts are per-retailer data.
Demos: scenario-a-baseline (standard store, one missing signage kit), scenario-b-escalation ("everything shipped, we're ready" - end-cap fixture the small format lacks, promo price ABOVE shelf on the hero SKU, two missing kits; ranking puts the mispricing first at 2x launch proximity).
Boundary: readiness pack + exceptions; no POS price, planogram, schedule or funding changes.
