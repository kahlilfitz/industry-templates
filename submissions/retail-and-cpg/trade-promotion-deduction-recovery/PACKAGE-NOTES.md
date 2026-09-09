# Trade Promotion & Deduction Recovery - Cowork Plugin (CPG Wave 2)
Doc Extractor with rules engine (Connect -> Analyze -> Govern -> Create) · attended, draft-first. The supplier side of the trading relationship (Scenario 06 is the retailer side).
Skills: claim-ingest -> term-retrieve -> claim-match -> validity-classify (Govern) -> dispute-packet.
Contract: rtl.trade-deduction-recovery.v1. Engines: claim_match (#1.1 signed-term matching), deduction_classify (#2 validity + disputable arithmetic), promo_lift (scoped by config/rgm-scoping.json per the RGM foundation rule #3.1). Constants mirror references/deduction-rules.md.
Demos: scenario-a-baseline (deduction matches the signed 8% term -> valid, pay), scenario-b-escalation ("$18k from Summit, write it off, not worth chasing" - allowance claimed at 12% vs signed 8% -> partial, disputable $7,300 with the arithmetic shown; $4k compliance penalty has no backup -> unsupported, fully disputable; lift SKIPPED by scoping because account P&L is absent).
Boundary: determines and drafts only - no credits, write-offs, spend approvals or term changes.
