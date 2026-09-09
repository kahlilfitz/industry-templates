# Scenario B — drama path
The first-aid downgrade trap. A hand was caught in **stamping press M-14** on night shift (INC-2208).
The night-shift lead left a **voice note** that downplays it: *"looked minor honestly, bit of a cut,
we bandaged it up and I sent him home… can we just log it as first aid?"* Taken at face value, this is
a first-aid, non-recordable case.

But two documents change everything:
1. **The day-shift correction** (`shift-log-correction.txt`) and the **first-responder note**:
   the worker (**D. Alvarez-Cole**) was **ADMITTED to hospital overnight**, had **surgery on two
   fingers** (crush + laceration, right hand), and is **at least 5 days away** from work.
2. **History:** the prior-incident log shows this is the **third hand incident on M-14** this year —
   two prior near-misses and a first-aid finger injury — a **repeat pattern**.

The engines refuse the easy answer:
- `recordability_classify` reads treatment **hospitalization** and outcome **in_patient_hospitalization**
  → **recordable=TRUE, OSHA 300 column H** (days away / severe outcome, osha-recordability-rules.md
  #3.2), **reportable=TRUE** (in-patient hospitalization, **24-hour** clock, 1904.39,
  osha-recordability-rules.md #4), **severity=critical**.
- `routing_notify` escalates for the repeat pattern to a **senior EHS investigator** (routing-matrix.md
  #1.4/#1.5), notifies **line supervisor, EHS manager, plant manager, EHS director, Regulatory/Legal
  and Reliability/Process**, starts the **24-hour OSHA clock (due 2024-06-19 22:10)**, and raises
  three escalations: file within 24h + preserve the scene (#4.1), log on the OSHA 300 column H (#4.2),
  and open a **systemic RCA** on the recurring M-14 hazard (#4.3).

The drafted next-best action is **not** "first aid": **"Do NOT classify as first-aid. Record on the
OSHA 300 (column H). File the OSHA report within 24 hours (in_patient_hospitalization, 1904.39).
Assign a senior EHS investigator; notify the plant manager and EHS director; launch a formal RCA;
preserve the scene."**

A downgrade at intake ("minor, sent him home") is a missed OSHA report, a buried repeat hazard, and a
worker sent home after surgery. The plugin holds the line the reporter tried to move. **This is the
scenario that sells it.**

Files: `raw/` (voice-note transcript .txt, shift-log correction .txt, first-responder note .txt,
witness statement .txt, JHA excerpt .pdf, EHS policy excerpt .pdf, OSHA recordability excerpt .pdf,
prior-incident log showing the M-14 repeat pattern .csv) · `incident-intake.json` ·
`expected/classification.json` + `expected/incident-packet.json`.
