# Scenario A — happy path
The clean baseline. A packaging operator (**J. Ruiz**) slipped on a wet patch near the wash-down bay
on **Packaging Line 2**, caught herself on the rail, and slightly twisted her **left ankle**. She got
**first aid only** — an ice pack at the station — and returned to light duties. **No lost time, no
work restriction, no doctor visit.** The incident was reported the same day on a **form** (INC-2201).

The engines classify it proportionately:
- `recordability_classify` reads treatment **first_aid** and outcome **none** → **recordable=FALSE**
  ("first-aid only, no days away/restriction," osha-recordability-rules.md #2.1/#3.5), **reportable
  =FALSE**, **severity=low**. No OSHA 300 column, no regulatory clock.
- `routing_notify` routes to the **area / line supervisor** (routing-matrix.md #1.1) with a single
  owner notification, **no regulatory clock**, and **no escalations**.

The drafted next-best action is **"log as first-aid/near-miss (not OSHA recordable); investigate as a
leading indicator and feed any control back into the JHA."** The write-up is a clean DRAFT with a
5-Why RCA template — proportionate to a minor first-aid case.

This is what a correctly-handled minor incident looks like: reported, classified, routed and drafted
without over- or under-reacting. It is the contrast that makes Scenario B land.

Files: `raw/` (incident report form .txt, reporter email .txt, witness statement .txt, first-aid note
.txt, JHA excerpt .pdf, EHS policy excerpt .pdf, prior-incident log .csv) · `incident-intake.json` ·
`expected/classification.json` + `expected/incident-packet.json`.
