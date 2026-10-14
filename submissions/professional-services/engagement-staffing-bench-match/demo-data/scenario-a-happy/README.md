# Scenario A - happy path
The engagement has two open roles and a clean bench/conflicts extract. The engines should produce a ranked slate with an eligible first choice for both roles and no top-candidate Govern refusals.

Expected:
- `PSS-001` client delivery manager: Ava Morgan ranks first and remains eligible.
- `PSS-002` data migration consultant: Leo Brooks ranks first and remains eligible.
- Lower-ranked alternatives can still be held by availability: Ava needs review for the 80% data-migration role, and Mara is ineligible for that role. Those dispositions do not affect the two expected first-choice recommendations.

Start from `raw/` to exercise Connect, or from the structured `roles.json`, `bench.json` and `constraints.json` to exercise the deterministic engines. `expected/validated.json` is the slate-draft input after the secondary safety check. `expected/slate-draft.md` is the draft skeleton `slate_validate.py --draft-out` renders from it; the skill presents it verbatim.
