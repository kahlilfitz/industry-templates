# DELIVERABLE REVIEW PACKET - {{deliverable.deliverable_id}} - DRAFT

> Draft-first: this packet does not approve release, clear a gate, sign off the deliverable or substitute for reviewing-partner/QRM judgement.

Produced by deliverable-ingest -> criteria-retrieve -> assertion-map -> gate-check -> review-packet under contract `ps.deliverable-review-quality-gate.v1`.

## Release-readiness status
**{{release_readiness.status}}** - {{release_readiness.summary}}

## Gate checklist
| Gate | Status | Highest severity | Evidence |
|---|---|---|---|
{{for each gate_result}}| {{gate_id}} - {{name}} | {{status}} | {{highest_severity}} | {{citation}} |
{{end}}

## Ranked findings for partner review
| Rank | Severity | Gate | Location | Issue | Criteria |
|---|---|---|---|---|---|
{{for each ranked_finding}}| {{rank}} | {{severity}} | {{gate_id}} | p{{location.page}} / {{location.section}} / para {{location.paragraph}} | {{title}} - {{detail}} | {{criteria_section}} |
{{end}}

## Unsupported and limited assertions
{{for each assertion_mapping where support_status != "supported"}}
- **{{support_status}}** - {{assertion_id}} at p{{location.page}}, para {{location.paragraph}}: {{text}}
  - Evidence: {{evidence_ids}}
  - Rule: {{criteria_section}}; {{citation}}
{{end}}

## Required human decision
The reviewing partner/QRM owner decides whether fixes are sufficient. The engine can flag or block; it cannot clear the gate.

## Appendix - contract payload
```json
{{contract_payload}}
```
