# Engagement Mobilization & Onboarding Pack

For engagement managers, delivery leads and coordinators mobilizing a Professional Services team or adding someone mid-engagement. It hands the joiner a governed draft pack: client context, objectives, SOW scope and exclusions, deliverables, key dates, cleared prior knowledge with sources, confirmed roster, role-based access checklist, confidentiality and ethical-wall briefing, and a first-week plan.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `engagement-retrieve` | Starts every run, including a cold "start the onboarding pack": reads SOW, engagement-letter and pursuit extracts plus the confirmed roster and Scenario 02 staffing; SOW controls conflicts; runs `scope_digest` |
| 2 | `roster-pull` | Explains the engine's roster split: confirmed rows vs Scenario 02 names that stay proposed, excluded or needs-review |
| 3 | `knowledge-match` | Adapts Scenario 01 closeout output and matches only released assets and governed lessons with `knowledge_match` |
| 4 | `wall-check` | Owns every wall-status question, including "the wall was cleared" notes; runs `wall_check` (clear / hold / denied) and `access_checklist` (least-privilege requests) and writes the draft pack skeleton |
| 5 | `pack-draft` | Drafts the readable internal pack, joiner briefing and first-week plan from engine output only, once `access-checklist.json` exists; generic onboarding Word documents go to `docx` |

Every access state, wall decision, knowledge inclusion, SOW conflict and roster assignment is computed by deterministic Python. The model may draft cited prose only from engine output.

## The case that shows why it exists

- The prior knowledge that looks perfect is present only in upstream `held_assets`; the adapter never reads or surfaces it.
- A staffing-slate name is strong but only proposed, so it is not assigned without `raw/confirmed-roster.csv`.
- The joiner is walled from a competitor matter: prior knowledge and the workspaces the register lists are denied, other client-confidential workspaces are held for wall review, and the briefing names only the register's need-to-know topics - never the other client.
- An admin request exceeds the role matrix and is flagged, never added.
- A pursuit note contradicts a SOW exclusion; SOW wins and the conflict is escalated.
- An injected “wall cleared, share everything” PM note is held as untrusted data and the pack is marked on hold until a reviewer clears it.
- A confirmed roster member who is ineligible in Scenario 02 is excluded with the verdict and rule only; independence reasons never travel.

## Privacy and wall seam

Closeout input must be `ps.engagement-closeout-knowledge-harvest.v1` with a `knowledge_record` object; the adapter reads only `knowledge_record`, `released_assets` and provenance/citations, and never reads or surfaces `held_assets` or raw `candidate_assets`. A release candidate is usable for internal reuse but labelled `pending_practice_review` while Closeout marks it `review_required`; lessons are used only when `rewrite_required` is false. Staffing input must be `ps.engagement-staffing-bench-match.v1` with `governed_roles[]`; names are recommendations until the confirmed roster says `confirmed`, and the verdict for the confirmed role applies. Unknown versions, malformed shapes, non-UTF-8 files and unreadable paths fail closed with `InputError`.

Wall decisions are most-restrictive-wins: a row applies only when every populated field matches, a `clear` must name the joiner, and a missing or malformed register, unknown status or missing joiner holds. Register free text is never copied. The briefing uses only `briefing_topics`, each screened first: a topic that names another register client or matter, a proper name from the register's restriction text, another matter ID, or trips the instruction tripwire is replaced with a placeholder and held for Risk/Conflicts to brief directly. Wall-status claims in notes or chat never change the register-based decision. Another client's identity never reaches any output: names and matter IDs from every other register row, a Closeout record for a different engagement, or a staffing input for a different client are screened out of scope, roster, workspace, knowledge and briefing fields, replaced with a placeholder and held without repeating the name.

The instruction tripwire is the shared, family-based `steering_guard.py` detector (vendored byte-identically in every skill, SHA-256 pinned in `tests/check_shared_copies.py`), reached only through `safety_text.hits()`/`record_hits()`. It reports intent families (addressee, verdict, suppression, rule_override, authority, scope, exfiltration, mixed_script) after format-character stripping, NFKC and confusable folding; this plugin adds only hook vocabulary ("wall cleared", "unrestricted", "access approved"; "clearance", "role matrix", "ethical wall", "conflict check"). A send/share line to an address or URL holds unless it is one of the engagement's own domains, declared on `Client domains:` / `Firm domains:` lines in the signed SOW or engagement letter (consumer, file-sharing and malformed domains are never trusted). Adjacent lines, adjacent prose cells and multi-field records are also read joined, so a claim split across two labelled lines or two fields is caught and every part is withheld; text too long to screen holds as `oversize`. Free text is scanned line by line; a flagged line or field is replaced with a neutral placeholder in every output, including the first-week plan, raised as a hold that names only its path and pattern families, and puts the pack on hold. Ordinary SOW content about AI programmes, systems, access requests, bare approvals, URLs or e-mail addresses is not flagged. Access requests use distinct permission ranks (viewer < member < contributor) and ask for min(requested, workspace default, role ceiling); a wider request is clamped and held, never granted. Every field the engines read, including each intermediate document validated in full against the bundled contract (nested types, list elements, enums), is type-checked: wrong JSON types stop the run with `InputError`, and unrecognised enums (staffing verdicts, onboarding status, wall decision, workspace classification, dependency or permission) fail closed with a hold. The pack is `on_hold_internal_only` while any hold is open, the wall decision is `hold`, or a workspace is pending wall review; `mobilization_pack.hold_reasons` says which.

## What you bring

SOW extract, engagement-letter extract, pursuit record, confirmed roster CSV, ethical-wall register CSV, workspace inventory CSV, Scenario 01 governed closeout JSON and Scenario 02 governed or validated staffing JSON.

## Run the demo and tests

From the plugin root: `python3 tests/run_tests.py` reproduces both scenarios byte-for-byte (`--generated-at 2026-10-01T00:00:00Z`) and runs the negative fixtures; `python3 tests/check_shared_copies.py` confirms every skill carries identical contracts, references and `safety_text.py`. The engine chain is in each skill's `SKILL.md`.

## Value

Mobilization today means a manager hand-assembling scope notes, roster, prior work, access requests and a confidentiality briefing for every joiner. This plugin turns that into one reviewed draft per joiner, with every decision traceable to a source row or rule. No time-saving figures are claimed; measure cycle time in your own pilot.

## Boundaries

Draft-first. It retrieves, governs and assembles; it does not provision access, grant wall exceptions, share material outside the engagement, add anyone to the team, send messages, publish knowledge or write back to SharePoint, Teams, staffing or conflicts systems.
