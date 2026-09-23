# Conflicts & Independence Pre-Check — {{pursuit_id}}

> **DRAFT — HUMAN QRM REVIEW REQUIRED.** This packet assembles a proposed position only. It does not clear a conflict, waive independence, accept an engagement, approve a pursuit, file a record or overrule QRM.

Produced by `party-intake` -> `entity-resolve` -> `register-search` -> `conflict-classify` -> `clearance-memo` under contract `ps.conflicts-independence-precheck.v1`.

{{if escalations}}## 1. Open escalations / holds
{{for each escalation}}- {{escalation}}
{{end}}{{end}}

## 2. Proposed position for reviewer

**Engine position:** {{precheck_position.position}}  
**Required output:** {{precheck_position.draft_output}}  
**Human clearance required:** {{precheck_position.human_clearance_required}}  
**Citation:** {{precheck_position.citation}}

Use only the engine language. If there are no hits, state: **"No hits found in the registers searched, subject to review."** Do not state "cleared", "approved", "no conflict" or "OK to proceed".

## 3. Search scope actually covered

| Scope item | Value |
|---|---|
| Registers searched | {{search_scope.registers_searched}} |
| Date range | {{search_scope.date_range}} |
| Entity variants tried | {{search_scope.entity_variants_by_party}} |
| Corporate-family IDs included | {{search_scope.corporate_family_entity_ids}} |
| Unresolved parties | {{search_scope.unresolved_parties}} |
| Scope citation | {{search_scope.citation}} |

## 4. Resolved entities and family scope

| Intake party | Match status | Resolved / candidate entity | Score | Parent / family | Rule |
|---|---|---|---|---|---|
{{for each resolved_entity}}| {{given_name}} | {{match_status}} | {{resolved_legal_name}}{{candidate_legal_name}} | {{confidence}} | {{ultimate_parent_name}} | {{rule}} |
{{end}}

## 5. Hits and governing rule

| Hit | Register | Type | Matched entity | Relationship | Waiver / wall posture | Required action | Rule |
|---|---|---|---|---|---|---|---|
{{for each conflict_hit}}| {{hit_id}} | {{register}} | {{conflict_type}} | {{matched_entity}} | {{relationship}} | {{waiver_posture}} / {{ethical_wall_recommendation}} | {{required_action}} | {{rule}} |
{{end}}

## 6. Draft reviewer notes

- The classification above is deterministic engine output. Do not edit the conflict type, waiver posture or required action except by rerunning the engine on corrected evidence.
- Required consent, ethical-wall and refusal-position language are recommendations for human QRM review only.
- If the reviewer adopts a position, record the controlled QRM decision outside this draft.

## Appendix A — contract payload

```json
{{contract_payload}}
```
