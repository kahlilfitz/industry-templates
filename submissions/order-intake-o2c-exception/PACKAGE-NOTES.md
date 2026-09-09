# Order Intake & O2C Exception - Cowork Plugin (Retail Wave 2, heavy CPG usage)
Intake & Triage to Automate (Connect -> Analyze -> Act -> Create) · ships at action level L0-L2; creation/release human-approved until the customer promotes in config/. Clearest attended->autonomous promotion path in the set.
Skills: order-ingest -> line-normalize -> order-validate -> exception-route -> response-draft.
Contract: rtl.order-intake-o2c.v1. Engines: order_validate (#1 identity, #2 UOM/qty, #3 price, #4 credit), exception_route (queues + corrections, #5 action levels). Constants mirror references/o2c-rules.md; tolerances and the action level live in config/.
Demos: scenario-a-baseline (clean emailed order -> validated file + confirmation), scenario-b-escalation ("regular customer, truck leaves at 2, just key it" - ambiguous alias, 500 EA from a cases-of-24 customer, 12% price dip with no promo ref, credit limit breach -> 4 exceptions routed with corrections; one clarification message drafted).
