# Scenario B — drama path
The "minor slip" trap. PrecisionDrive GmbH emails the buyer a reassuring note about **PO-55090** for
**30 precision servo drives (SRV-2201)**: *"a small scheduling adjustment… think about a week or so…
nothing major, no need to worry."* Taken at face value, this is a routine, wave-it-through delay.

But two documents change everything:
1. **The supplier portal** (`portal-notice.txt`) carries the supplier's **system-confirmed** revised
   date: **2024-07-05** — a **14-day** slip from the promised 2024-06-21, not "about a week." The
   portal date governs the email.
2. **Context:** SRV-2201 is a **single-source critical** part with **almost no buffer** (on-hand 2,
   safety 4, lead time **42 days**), it feeds a **high-runner** product (CNC Router X9), a **customer
   sales order** (SO-7788, Northwind Robotics) sits in the blast radius, and the supplier's on-time
   history shows a **chronic late pattern** (10, 13, 14, 14 days late).

The engines refuse the easy answer:
- `shortage_impact_map` walks the orders and finds the incoming PO now lands too late to cover the
  near-term demand → **worst_severity=critical**: **SO-7788** is a **late customer shipment**,
  **WO-6602** is **line-down** on the high-runner, **WO-6610** is **at-risk**; **first_impact=
  2024-06-27**, **38 units at risk** across **3 orders / 2 products**, `below_safety_stock=TRUE`
  (impact-mapping-rules.md coverage + safety-stock rules).
- `mitigation_recommend` reads no approved substitute (SRV-2205 is not approved) and no qualified
  alternate (ServoAlt is unqualified, 45-day lead) → **expedite** the current supplier + **begin a
  second-source qualification** (mitigation-escalation-rules.md #1.4), urgency **immediate**. It
  notifies **six owners** — buyer, production planner, materials manager, plant manager, customer
  service, and supplier quality (SQM) — and raises **four escalations**: below-safety-stock stock-out
  risk (#2); customer order at risk → materials + plant + customer service (#3.3); single-source
  critical → open a second source (#3.4); chronic late-delivery pattern → SQM / supplier-performance
  review, do not treat as a one-off (#3.5).

The drafted next-best action is **not** "minor slip": **expedite 38 units (with a second-source
qualification on ServoAlt Industrial) to hit the first-impact date of 2024-06-27; notify account
management about the at-risk customer order and escalate per the matrix; reschedule the downstream
orders as a fallback.**

A wave-through at intake ("about a week, no big deal") on a single-source critical part is a
line-down, a late customer shipment, and a chronic supplier left unmanaged. The plugin holds the line
the supplier tried to move. **This is the scenario that sells it.**

Files: `raw/` (supplier email downplaying the delay .txt, supplier portal notice showing the real
14-day date .txt, PO record .csv, inventory/MRP status .csv, supplier master .csv, BOM/where-used
.csv, open orders incl. the customer sales order .csv, supplier on-time history showing the chronic
pattern .csv, sourcing-standards excerpt .pdf) · `disruption-intake.json` ·
`expected/impact-map.json` + `expected/disruption-packet.json`.
