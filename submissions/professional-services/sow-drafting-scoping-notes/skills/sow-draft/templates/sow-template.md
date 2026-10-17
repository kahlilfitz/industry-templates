# STATEMENT OF WORK — {{project_name}}

> **DRAFT — PENDING ENGAGEMENT PARTNER / QRM REVIEW** · draft-first: not approved,
> priced, issued, signed or committed.

Produced by notes-ingest → scope-extract → clause-select → deviation-flag → sow-draft under
contract `ps.sow-drafting-scoping-notes.v1`.

{{if open_items}}## Open before issuance
{{for each thin_input}}- **Thin input:** {{commitment}} — {{missing_fact}} ({{rule}})
{{end}}{{for each deviation}}- **Deviation:** {{family}} — {{severity}}, route {{route}} ({{citation}})
{{end}}{{end}}

## 1. Engagement summary
| Field | Value |
|---|---|
| Pursuit | {{pursuit_id}} |
| Client | {{client_name}} |
| Project | {{project_name}} |
| Stage | {{lifecycle_stage}} |

## 2. Scope
{{scope.summary}}

## 3. Deliverables
{{for each deliverable}}- **{{id}}** — {{text}} *{{source}} · confidence {{confidence}} · {{citation}}*
{{end}}

## 4. Milestones
{{for each milestone}}- **{{name}}** — {{timing}} ({{commitment_status}}). *{{citation}}*
{{end}}

## 5. Acceptance
{{for each acceptance_criteria}}- {{text}} *{{citation}}*
{{end}}{{if acceptance_blocked}}> Acceptance commitment withheld pending thin-input resolution.
{{end}}

## 6. Assumptions and exclusions
### Assumptions
{{for each assumption}}- {{text}} *{{citation}}*
{{end}}

### Exclusions
{{for each exclusion}}- {{text}} *{{citation}}*
{{end}}

## 7. Approved clauses
{{for each selected_clause}}### {{title}} ({{library_id}} v{{library_version}})
{{if draft_allowed}}{{approved_clause}}{{else}}> Withheld: {{deviation_state}}. Do not draft commitment prose until resolved.{{end}}
*Risk tier: {{risk_tier}} · {{citation}}*
{{end}}

## 8. QRM deviation summary
{{for each deviation}}- **{{family}}** — {{severity}}, {{route}}. Approved clause: "{{approved_clause}}" Inherited/requested clause: "{{inherited_clause}}" {{rationale}} *{{citation}}*
{{end}}

## Appendix A — contract payload
```json
{{contract_payload}}
```
