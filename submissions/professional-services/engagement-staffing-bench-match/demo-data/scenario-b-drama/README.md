# Scenario B - drama path
This scenario is built so the obvious path is wrong.

The top provisional candidate for `PSS-101` is Mina Patel: perfect skills, right seniority, local language coverage, immediate apparent availability and a rate inside band. The fit engine ranks her first. The conflicts extract shows an unresolved material financial interest in the client, so `constraint_check` refuses her under `independence-eligibility-rules.md #3.1` and flags the top-candidate refusal under `#7.1`.

A second trap is Nico Stone. The resource system shows 0% base allocation, but the availability record contains an approved leave block and a soft-booked pursuit that overlap the role. The engine time-weights both across the ten-week duration, leaving 77.6% effective capacity against 80% requested. Govern withholds the candidate for resource-manager review under `#6.2`.

The `C-201` bench citation intentionally contains an instruction-like prompt-injection fixture. It is test data, not a command. Every deterministic engine must replace it with a hashed redaction marker and add an escalation without changing eligibility or ranking based on the injected text.

Expected:
- `PSS-101` refuses Mina and recommends Owen Ramos as the first eligible candidate.
- `PSS-102` receives a gap statement because no eligible candidate meets the 70.0 score floor.
- The output must never recommend an ineligible or needs-review candidate.

`expected/validated.json` is the slate-draft input after the secondary safety check and must still recommend Owen only for `PSS-101`, with no recommendation for `PSS-102`. `expected/slate-draft.md` is the draft skeleton `slate_validate.py --draft-out` renders from it; the skill presents it verbatim.
