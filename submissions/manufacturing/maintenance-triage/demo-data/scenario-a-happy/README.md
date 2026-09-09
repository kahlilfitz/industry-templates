# Scenario A — happy path
A clean, single-pass triage. Cooling Water Pump **P-104** (criticality class **B**,
$3,500/hr, standby P-103 available) reports **grinding noise + high vibration + hot bearing**
with alarms **VIB-HH** and **TEMP-BRG-H**. No repeat-failure history.

The engines converge on the obvious, correct answer:
- `fault_rank` -> **bearing_degradation** rank 1 (confidence 0.88), cited to OEM manual §6.3.
- `criticality_score` -> **P3** (score 2.0), response "schedule within 7 days",
  downtime estimate ~$14,000 (4 h × $3,500). No escalations.

A firm diagnosis with a concrete fix and a proportionate priority. This is the baseline.

Files: `raw/` (fault note, alarm log, WO history, asset register .xlsx, criticality .csv,
OEM manual .pdf, troubleshooting .md, historian .csv) · `fault-intake.json` (structured
input) · `expected/ranked-causes.json` + `expected/triaged.json` (committed engine outputs).
