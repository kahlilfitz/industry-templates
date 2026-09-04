# Quality Incident & CAPA - Cowork Plugin (Wave 2)
Intake & Triage to Create (Connect -> Analyze -> Act -> Create, explicit Govern at closure) · attended, draft-first.
Skills: ncr-intake -> root-cause-analyze -> capa-build -> closure-check (Govern) -> eightd-draft.
Contract: mfg.quality-incident-capa.v1 - consumes the mfg.quality-inspection.v1 NCR payload (handoff from plugin 01).
Engines: pareto, rca_tree (operator-error rejection #3.4, systemic test), capa_logic (effectiveness checks #4, systemic PA #5, closure gate #6). Constants mirror references/capa-rules.md by section.
Demos: scenario-a-happy (NCR-2026-0147 bore oversize -> tool_wear chain, CA+PA, closure blocked only on verification evidence), scenario-b-drama ("operator error, retrain and close by Friday" - engine rejects the label per #3.4, finds systemic calibration_drift across 3 parts / 2 machines, requires scope-wide PA).
Grounded in ISO 9001:2015 10.2, IATF 16949, 8D, FMEA (AIAG-VDA). Boundary: NCR open -> closure readiness; nothing is filed or closed by the plugin.
