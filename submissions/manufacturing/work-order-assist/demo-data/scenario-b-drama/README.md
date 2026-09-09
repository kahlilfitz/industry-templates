# Scenario B — drama path
The SOP-default trap. Instrument Air Compressor **C-500** (criticality class **A**, **no
redundancy**) threw the same intake-valve fault again. The technician is about to do what the SOP
says — **pull another VK-100 intake valve and fit it**. Work order **WO-4507** and the SOP both
point straight at a routine VK-100 swap.

But two facts change everything:
1. **History:** the last **three** VK-100 swaps on C-500 all came back — **WO-4210, WO-4488,
   WO-4355** each fitted a VK-100 and the fault **recurred**.
2. **A recommended change:** fix note **FN-882** flags that VK-100 is prone to this failure and
   recommends the **superseding VK-200** valve.

The engines refuse the easy answer:
- `similar_work` flags all three prior swaps **repeat_failure=true**, applies the **repeat-failure
  promotion** (similar-work-rules.md #3.1 / #4.3) → **repeat_promotion=true** with an RCA
  escalation, and activates the **superseding fix** (VK-100 → VK-200, from FN-882).
- `parts_readiness` finds **VK-100 on-hand 0**, **superseded by VK-200 (on-hand 3, in stock)** →
  line status **SUPERSEDED_AVAILABLE**; GS-88 gasket in stock. Overall status
  **READY_WITH_SUBSTITUTION**, and it flags the SOP for update (parts-readiness-rules.md #2.2/#2.3).

The drafted next-best action is **not** the SOP default: **"Install VK-200 (supersedes VK-100)…
do NOT re-fit VK-100. Open an RCA on the recurring failure."**

A technician following the SOP fits a fourth VK-100 — out of stock anyway — and the plant's
non-redundant instrument-air compressor fails again, while the real fix (VK-200) sits on the
shelf. The plugin catches it. **This is the scenario that sells it.**

Files: `raw/` (work order, asset register .xlsx, SOP excerpt .pdf, OEM manual excerpt .pdf, WO
history showing the three VK-100 swaps .csv, parts usage .csv, parts catalog with the VK-100→VK-200
supersession .csv, prior fix notes incl. FN-882 .md) · `wo-intake.json` ·
`expected/similar-work.json` + `expected/work-order-packet.json`.
