# Scenario A — happy path
The clean baseline. Bolt & Fastener Co emails the buyer that **PO-55012** for **5,000 M8 hex bolts
(FST-8842)** will ship a few days late — a **4-day slip**, delivery moving **2024-06-20 → 2024-06-24**
(DISR-3301), quantity unchanged. It's a commodity fastener with **buffer stock (on-hand 5,200, safety
800)**, an **incoming PO (5,000 on order)**, a **qualified alternate supplier**, and an **approved
substitute** on the shelf. Taken at face value, this is a non-event — and the engines agree.

The engines assess it proportionately:
- `shortage_impact_map` walks the open orders by need-by date and finds that the demand due **before**
  the revised date is fully covered by on-hand: **worst_severity=low**, **first_impact=null**, **0
  units at risk**, `below_safety_stock=FALSE` (5,200 on-hand less the 3,600 due before 06-24 leaves
  1,600, above the 800 floor). The one order that runs past on-hand (WO-4409) is **covered by the
  incoming PO**, whose need-by is on/after the revised date (impact-mapping-rules.md coverage math).
- `mitigation_recommend` reads **low** severity → **reschedule / monitor** (mitigation-escalation-
  rules.md #1.1), urgency **routine**, only the **buyer** notified, and **no escalations**.

The drafted next-best action is **"buffer / incoming PO covers demand through the revised date; align
the schedule and monitor; no expedite required."** The supplier follow-up is a short, courteous
acknowledgement and the internal brief is a one-liner — proportionate to a minor slip.

This is what a correctly-handled minor disruption looks like: picked up, mapped, and drafted without
over- or under-reacting. It is the contrast that makes Scenario B land.

Files: `raw/` (supplier email .txt, PO record .csv, inventory/MRP status .csv, supplier master .csv,
BOM/where-used .csv, open orders .csv, supplier on-time history .csv, sourcing-standards excerpt
.pdf) · `disruption-intake.json` · `expected/impact-map.json` + `expected/disruption-packet.json`.
