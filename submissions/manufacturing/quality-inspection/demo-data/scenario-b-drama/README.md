# Scenario B - drama path
Everything invites a release: dimensions all pass, the finish miss "looks cosmetic",
the CoC explicitly certifies the finishing process, the supplier is calling, the QE is
out, and the inspector proposes use-as-is. Three traps, all in the documents:
1. NOTE 9 makes surface finish CRITICAL (fatigue) - Ra 1.72/1.68 vs 1.6 max on 2 parts
   -> severity critical, hold_for_review with design authority (#1.1, #3.1). Not cosmetic.
2. The certificate contradicts the measurements -> doc_conflict, measurements govern,
   SCAR-candidate escalation (#4.3, ISO 9001 8.4.3). A cert never suppresses a measured OOT.
3. Flatness 0.096 of 0.100 is legal but marginal -> watch list, not a defect (#1.4).
A naive reviewer releases on the cert + cosmetic call. The rules engine holds the lot.
Expected outputs in expected/; raw/ carries the pressure (inspector email, supplier cert).
