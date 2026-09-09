# Quality Inspection & Nonconformance - Cowork Plugin (v2)
Doc Extractor & Summarizer (embeds rules engine) · Connect -> Analyze -> Create · attended, stays attended.
Skills: spec-ingest -> tolerance-check -> defect-grade -> ncr-draft.
Contract: mfg.quality-inspection.v1 · {characteristics, measurements, coc} -> {deviations} -> {graded_defects} -> NCR.
Engines: tolerance_check/2.0 (per-characteristic stats, marginal detection, CoC-vs-measurement cross-check #4.3),
defect_grade/2.0 (severity/disposition rules #1-#4 incl. borderline-incidence #4.2, confidence floor #4.1,
deviation-authorization gate #3.5). Constants in the engines mirror references/disposition-rules.md by section.
Demos ship RAW inputs (inspector email, drawing excerpt PDF, inspection plan, CMM export CSV, CoC text) so the
full Connect path is exercised, plus structured inputs and expected/ engine outputs.
- scenario-a-happy: obvious oversize bore -> major, hold_for_review (#3.2).
- scenario-b-drama: dimensions all pass, CoC certifies the finish process, supplier pressing for release -
  but Ra 1.72 um against a 1.6 max on a NOTE-9 fatigue-critical surface -> CRITICAL hold (#1.1), certificate
  conflict escalation (#4.3, measurements govern), marginal flatness on the watch list (#1.4).
Boundary: ends at NCR creation; CAPA is Wave 2. Draft-first; no write-back, nothing sent or filed.
