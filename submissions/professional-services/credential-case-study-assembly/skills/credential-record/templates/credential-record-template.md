# Credential Record — {{engagement.engagement_id}}

> **DRAFT — PENDING REFERENCE OWNER / LEGAL APPROVAL**. This record is prepared for review only; it does not publish, approve external use, clear a client name or assert unverified figures.

Produced by closeout-retrieve -> credential-draft -> permission-check -> anonymize-variant -> credential-record under contract `ps.credential-case-study-assembly.v1`.

## 1. Clearance summary
| Field | Value |
|---|---|
| Requested use | {{request.requested_use}} |
| Naming status | {{permission_verdict.naming_status}} |
| Governing clause | {{permission_verdict.name_governing_clause}} |
| Logo status | {{permission_verdict.logo_status}} |
| Testimonial status | {{permission_verdict.testimonial_status}} |
| Anonymised variant required | {{permission_verdict.anonymised_variant_required}} |
| Proposed descriptor status | {{permission_verdict.proposed_descriptor_status}} |

{{if permission_verdict.escalations}}## 2. Open escalations
{{for each permission_verdict.escalations}}- {{escalation}}
{{end}}{{end}}

## 3. Credential taxonomy
| Field | Value | Confidence | Citation |
|---|---|---|---|
| Sector | {{taxonomy_match.sector.value}} | {{taxonomy_match.sector.confidence}} | {{taxonomy_match.sector.citation}} |
| Service line | {{taxonomy_match.service_line.value}} | {{taxonomy_match.service_line.confidence}} | {{taxonomy_match.service_line.citation}} |
| Capability | {{taxonomy_match.capability.value}} | {{taxonomy_match.capability.confidence}} | {{taxonomy_match.capability.citation}} |
| Size band | {{taxonomy_match.engagement_size_band.value}} | {{taxonomy_match.engagement_size_band.confidence}} | {{taxonomy_match.engagement_size_band.citation}} |
| Outcome type | {{taxonomy_match.outcome_type.value}} | {{taxonomy_match.outcome_type.confidence}} | {{taxonomy_match.outcome_type.citation}} |

## 4. Credential entry draft
{{credential_entry_copy}}

## 5. Case-study copy
### Short form
{{case_study_short}}

### Medium form
{{case_study_medium}}

### Long form
{{case_study_long}}

{{if permission_verdict.anonymised_variant_required}}## 6. Anonymised variant
Use descriptor: **{{permission_verdict.safe_descriptor}}**.

{{anonymised_case_study_copy}}
{{end}}

## 7. Cleared figures — allowed in publishable copy
{{for each permission_verdict.cleared_figures}}- {{metric}}: {{value}} {{unit}} — {{clearance_rationale}} · {{governing_clause}}
{{end}}

## 8. Uncleared figures — not for publishable copy
{{for each permission_verdict.uncleared_figures}}- {{metric}}: {{value}} {{unit}} — {{clearance_rationale}} · {{governing_clause}}
{{end}}

## Appendix A — governed contract payload
```json
{{contract_payload}}
```
