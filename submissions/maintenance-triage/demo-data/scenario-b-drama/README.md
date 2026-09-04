# Scenario B — drama path
The hidden root cause. Boiler Feed Water Pump **P-201** (criticality class **A**,
$12,000/hr, **no redundancy**) "tripped on overload again." The technician is about to do
what worked the last three times — **reset the overload relay and move on**. The alarm in
front of them (OL-TRIP) and the obvious fix both point to a cheap electrical reset.

But two facts change everything:
1. **History:** three `motor_overload_electrical` resets in **78 days** (WO-30112, -30455, -30890).
2. **A new signal:** a **VIB-HH** vibration alarm appeared for the first time this event, and
   the historian shows vibration climbing across the quarter.

The engines refuse the easy answer:
- `fault_rank` applies the **repeat-failure promotion** (failure-mode-library.md #3.1):
  a recurring symptomatic fix + emerging mechanical signals means the reset is masking a
  root cause. It **promotes bearing_degradation to rank 1** (confidence 0.90), demotes
  `motor_overload_electrical` to a symptom, and raises an RCA escalation.
- `criticality_score` escalates to **P1** (score 6.0): class A base + $12k/hr downtime +
  repeat-failure factor + mechanical-root-on-class-A + no redundancy. Downtime estimate
  ~$48,000, immediate supervisor escalation.

A naive triage resets the relay a fourth time and the pump fails again — on the plant's most
critical, non-redundant asset. The plugin catches it. **This is the scenario that sells it.**

Files: `raw/` (fault note, alarm log with the repeat OL-TRIPs, WO history showing the three
resets, asset register .xlsx, criticality .csv, OEM manual .pdf, troubleshooting .md,
historian .csv) · `fault-intake.json` · `expected/ranked-causes.json` + `expected/triaged.json`.
