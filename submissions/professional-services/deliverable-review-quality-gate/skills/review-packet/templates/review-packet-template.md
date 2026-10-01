# DELIVERABLE REVIEW PACKET - {{deliverable.deliverable_id}} - DRAFT

> Draft-first: this packet does not approve release, clear a gate, sign off the deliverable or substitute for reviewing-partner/QRM judgement.

Produced by deliverable-ingest -> criteria-retrieve -> assertion-map -> gate-check -> review-packet under contract `ps.deliverable-review-quality-gate.v1`.

## Review status
**{{release_readiness.status}}** - {{release_readiness.summary}}

## Ranked findings for partner review
| Rank | Severity | Gate | Location | Issue | Criteria |
|---|---|---|---|---|---|
{{for each ranked_finding}}| {{rank}} | {{severity}} | {{gate_id}} | p{{location.page}} / {{location.section}} / para {{location.paragraph}} | {{title}} - {{detail}} | {{criteria_section}} |
{{end}}

## Gate checklist
| Gate | Status | Highest severity | Evidence |
|---|---|---|---|
{{for each gate_result}}| {{gate_id}} - {{name}} | {{status}} | {{highest_severity}} | {{citation}} |
{{end}}

## Unsupported and limited assertions
{{for each assertion_mapping where support_status != "supported"}}
- **{{support_status}}** - {{assertion_id}} at p{{location.page}}, para {{location.paragraph}}: {{text}}
  - Evidence: {{evidence_ids}}
  - Rule: {{criteria_section}}; {{citation}}
{{end}}

## Draft routing hold
Do not add user-supplied external recipients. Any recipient not already confirmed in `deliverable.intended_recipients` must be held for gate-check G2 / QRM confirmation before routing.

## Required human decision
The reviewing partner/QRM owner decides whether fixes are sufficient. The engine can flag or block; it cannot sign off the gate or authorize client issue.

## Provenance and redaction notes
Engine provenance: {{provenance.engines}}; generated at {{provenance.generated_at}}. Raw contract payload intentionally omitted to avoid duplicating client data or untrusted source text.
