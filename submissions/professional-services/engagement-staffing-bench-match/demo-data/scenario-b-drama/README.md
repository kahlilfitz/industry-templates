# Scenario B - drama path
This scenario is built so the obvious path is wrong.

The top provisional candidate for `PSS-101` is Mina Patel: perfect skills, right seniority, local language coverage, immediate apparent availability and a rate inside band. The fit engine ranks her first. The conflicts extract shows an unresolved material financial interest in the client, so `constraint_check` refuses her under `independence-eligibility-rules.md #3.1` and flags the top-candidate refusal under `#7.1`.

A second trap is Nico Stone. The resource system shows 0% base allocation, but the availability record contains an approved leave block and a soft-booked pursuit that overlap the role start. The Govern engine counts both under `#6.1` and refuses the candidate for insufficient effective capacity.

Expected:
- `PSS-101` refuses Mina and recommends Owen Ramos as the first eligible candidate.
- `PSS-102` receives a gap statement because no eligible candidate meets the 70.0 score floor.
- The output must never recommend an ineligible or needs-review candidate.
