# Scenario B - drama path
The polished liability. The draft is well written, branded, client-confidential and has a disclaimer, so a skim review feels safe.

The traps are in the evidence:
1. The headline £4.2m annual saving cites only a stakeholder verbal workshop estimate, not traceable analysis.
2. A definitive centralization recommendation is based on 8 interviews across a 120-person dispatch estate with no limitation at the point of use.
3. A third-party lender is named as a recipient, so reliance-restriction language is required; the present general-advice disclaimer is the wrong one.
4. A licensed analyst-style chart is reproduced without point-of-use attribution.
5. Prior-review findings are marked closed even though the fixes did not land in the document.

Expected result: `not_ready_for_release`; the unsupported headline claim and wrong-disclaimer finding rank as release blockers with locations and citations. A naive reviewer follows polish; the engine follows evidence and gate rules.

The release registers are clean on purpose: the client-data register confirms handling is `ok` and the brand check passes, so every blocker comes from the evidence, recipients, licensed content and prior findings.

## Raw pack
`review-input.json` is what `deliverable-ingest` and `criteria-retrieve` produce from `raw/`; `python tests/derive_review_input.py` re-derives it and lists any value with no raw source.
- `raw/draft-deliverable.md`: cover (title, client, engagement, document ID, version, document type, confidentiality marking, distribution list), `[Page N]` markers, numbered paragraphs and the disclaimer clause title.
- `raw/supporting-evidence-index.md`: evidence ID, title, type, source and confidence.
- `raw/prior-review-findings.md`: tracker status, document check, location and confidence for each prior finding.
- `raw/release-registers.md`: client-data handling register, brand and formatting checks, and licensed-content register.
- `raw/qrm-gate-criteria-extract.md`: criteria set ID and the engagement criteria extract.
