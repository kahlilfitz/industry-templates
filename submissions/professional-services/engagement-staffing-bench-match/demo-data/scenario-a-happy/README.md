# Scenario A - happy path
The engagement has two open roles and a clean bench/conflicts extract. The engines should produce a ranked slate with eligible candidates for both roles and no Govern refusals.

Expected:
- `PSS-001` client delivery manager: Ava Morgan ranks first and remains eligible.
- `PSS-002` data migration consultant: Leo Brooks ranks first and remains eligible.
- No candidate is blocked by independence, ethical-wall, prior-role or availability constraints.

Start from `raw/` to exercise Connect, or from the structured `roles.json`, `bench.json` and `constraints.json` to exercise the deterministic engines.
