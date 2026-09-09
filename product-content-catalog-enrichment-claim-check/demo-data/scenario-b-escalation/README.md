# Scenario B - escalation path
"Use the copy AS WRITTEN, launch Friday, their legal reviewed it." Expected:
1. GTIN 00055577788812 (sponge) FAILS the GS1 check digit -> record blocked (#1.1).
2. "kills 99.9%", "antibacterial", "biodegradable" are regulated terms with NO
   substantiation for these GTINs in the library -> regulated_blocked (#4.2); the
   supplier's own legal review is not our substantiation (#4.1). "Compostable" on the
   sponge likewise blocked.
3. The draft ships with approved attributes only; blocked claims never appear, not even
   softened (#4.3). Marketplace completeness gaps named (weight/country on SKU 2).
A naive enrichment pastes the romance copy; the Govern engine blocks it.
