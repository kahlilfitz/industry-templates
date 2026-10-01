# Changelog

## 1.0.0 - 2026-10-01

- Initial Wave 1 Scenario 03 plugin with `scope_digest`, `knowledge_match`, `wall_check` and `access_checklist`.
- Fail-closed adapters for Scenario 01 Closeout and Scenario 02 Staffing outputs, verified against the real sibling demo outputs: release candidates labelled `pending_practice_review`, lessons only when `rewrite_required` is false, malformed shapes raise `InputError`; Staffing verdicts per confirmed role (most restrictive otherwise), `needs_review` escalates, independence reasons never travel.
- Ethical-wall gate is most-restrictive-wins: AND matching on person/client/matter, `clear` must name the joiner, missing register / unknown status / no joiner hold; only listed workspaces are denied, other client-confidential or knowledge-dependent workspaces are held. Briefing uses `briefing_topics` only; register free text is never copied.
- Roster: blank `assignment_status` is not assigned; multiple joiners escalate; unknown roles request nothing and hold.
- Instruction tripwire tuned for mobilization data (0 false positives on 22 benign SOW/roster/inventory lines; catches 22 attack paraphrases incl. Cf and full-width evasions); flagged lines are withheld from the pack and the pack is marked `on_hold_internal_only`.
- Five distinct SKILL.md files with explicit sibling and cross-plugin deferrals; full contract schema with status enums.
- Two synthetic demo scenarios (Scenario A upstream mirrors the real Closeout shape), golden outputs, 50 shipped regression checks and a shared-copy check (`bundleTests: true`).
