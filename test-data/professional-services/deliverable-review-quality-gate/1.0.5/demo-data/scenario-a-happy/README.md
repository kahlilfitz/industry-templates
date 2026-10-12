# Scenario A - happy path
A well-prepared benefits-review draft. The quantified cycle-time and GBP 1.1m opportunity claims trace to signed client data and an approved benefits model; limitations and no-assurance language are present; confidentiality is marked correctly; the client-data register confirms handling is `ok`; and the licensed-content register is empty.

Expected result: `partner_review_required_advisories_only`. Gates clear with advisories only, chiefly the appendix footer formatting failure in the brand-check register, so the packet starts the partner at judgement rather than checklist chasing.

Without `raw/release-registers.md`, ingest would set `client_data_handling` to `unknown` and leave the brand and licensed-content registers unloaded, and gate-check would hold the release.

## Raw pack
`review-input.json` is what `deliverable-ingest` and `criteria-retrieve` produce from `raw/`; `python tests/derive_review_input.py` re-derives it and lists any value with no raw source.
- `raw/draft-deliverable.md`: cover (title, client, engagement, document ID, version, document type, confidentiality marking, distribution list), `[Page N]` markers, numbered paragraphs and the disclaimer clause title.
- `raw/supporting-evidence-index.md`: evidence ID, title, type, source and confidence.
- `raw/prior-review-findings.md`: tracker status, document check, location and confidence for each prior finding.
- `raw/release-registers.md`: client-data handling register, brand and formatting checks, and licensed-content register.
- `raw/qrm-gate-criteria-extract.md`: criteria set ID and the engagement criteria extract.
