# Scenario A — happy path
The clean baseline. Line 2 Case Conveyor Gearbox **CV-210** (criticality class **B**, redundant
**Line 3 available**) has an oil weep at the output shaft and a housing running warm; throughput
is unaffected. Work order **WO-4501** points to **SOP-LUBE-07** (gearbox oil-seal replacement).

Everything lines up the way a routine job should:
1. **SOP applies cleanly:** replace the output-shaft oil seal, renew the gear oil, replace the
   housing gasket, verify breather and oil level.
2. **A prior fix that worked:** the most similar past work, **WO-4120**, used exactly this remedy
   and had **no recurrence** (fix note FN-410).
3. **Parts on the shelf:** OS-45, GO-220 and GK-12 are all in stock above minimum.

The engines confirm the easy answer is the right one:
- `similar_work` ranks **WO-4120** top (similarity 0.46, confidence 0.84), **repeat_promotion =
  false**, no superseding fix — the standard remedy has a clean track record here.
- `parts_readiness` returns **READY** (3 lines, 0 blockers) — the job can start now.

The drafted next-best action is simply **"proceed per SOP-LUBE-07."** No escalations. This is the
baseline that proves the assistant assembles a correct, cited packet without crying wolf.

Files: `raw/` (work order, asset register .xlsx, SOP excerpt .pdf, OEM manual excerpt .pdf, WO
history .csv, parts usage .csv, parts catalog .csv, prior fix notes .md) · `wo-intake.json` ·
`expected/similar-work.json` + `expected/work-order-packet.json`.
