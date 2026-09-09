# Store Associate Assist - Cowork Plugin (Retail Wave 1)
Knowledge Assistant (Connect -> Analyze -> Create) · attended. The retail analogue of Manufacturing's Work Order Assistant.
Skills: question-intake -> policy-retrieve -> product-compare / promo-check -> answer-draft.
Contract: rtl.store-associate-assist.v1. Engines: policy_resolve (clause resolution #1, three-part promo test #2.1), product_compare (PIM-only comparison #3.1). Constants mirror references/assist-rules.md.
Config seam: config/ carries the customer's policy library, promo pack and PIM extract - swap per retailer, engines unchanged.
Demos: scenario-a-baseline (return question + coffee-maker comparison), scenario-b-escalation (price-match pressure on a marketplace listing + a promo that ended yesterday - exclusion clause PM-1.4 outranks, raincheck offered, manager escalation drafted).
Boundary: answers and drafts only - no price override, refund authorisation, inventory reservation or schedule change.
