# Professional Services Wave 1: operator's log

This is the operator's log and state of play for the five Professional Services Wave 1 plugins. It
records where each plugin stands, how it got there and what to do next, so that someone new can run
the work stream without a hand-over meeting.

The procedure for freezing, evaluating and archiving lives in
[Cowork evaluation workflow](../evaluation-workflow.md). The step-by-step routine for this work
stream lives in the [operator runbook](../operator-runbook.md). The failure classes every plugin is
hardened against live in the [plugin hardening checklist](../plugin-hardening-checklist.md). This
file is the history and the current position; it does not repeat those procedures.

State as of 2026-10-05, about 19:00 PT.

## Contents

- [Keeping this file current](#keeping-this-file-current)
- [Wave 1 definition of done](#wave-1-definition-of-done)
- [Status board](#status-board)
- [01 Engagement Closeout & Knowledge Harvest](#01-engagement-closeout--knowledge-harvest)
- [02 Engagement Staffing & Bench Match](#02-engagement-staffing--bench-match)
- [03 Engagement Mobilization & Onboarding Pack](#03-engagement-mobilization--onboarding-pack)
- [04 Time & Expense Narrative Compliance](#04-time--expense-narrative-compliance)
- [05 Deliverable Review & Quality Gate](#05-deliverable-review--quality-gate)
- [Lessons that changed the process](#lessons-that-changed-the-process)
- [Wave 2 queue and substitute](#wave-2-queue-and-substitute)
- [Open risks](#open-risks)
- [Frozen artefact register](#frozen-artefact-register)

## Keeping this file current

Update this file whenever one of these happens:

| Event | What to change |
|---|---|
| A candidate is frozen (`evaluation:prepare`) | Add a row to the plugin's version history with the version, commit, SHA-256 and "In Cowork evaluation". Add the full SHA-256 to the [frozen artefact register](#frozen-artefact-register). |
| A Cowork verdict is archived | Fill in the result, headline figures, key findings and archive path for that row. Update the status board. |
| A human reviewer signs off | Update the status board's done-conditions columns and the plugin's next action. Record only gate status (not started, in progress, passed, failed); reviewer names, per-prompt results and the owner's reasoning stay in the tracker. |
| The owner records a decision | Update the plugin's state and next action only: promoted, back to a new version, or stopped (not published). The decision record itself (who decided, when and why) stays in the tracker. |
| A distributable is promoted | Record the promoted file name and confirm its SHA-256 matches the evaluated ZIP. |
| A version is abandoned or superseded | Keep its row and say why (see T&E 1.0.2). |

Rules:

- One row per frozen or evaluated version. Never delete a row, including failed and superseded
  versions.
- Take figures from the archived `full-report.html` or the `evaluation-run.json` receipt, not from
  memory. If you cannot check something, write "(unverified)".
- This repository is public. Follow
  [What is public and what stays in SharePoint](../operator-runbook.md#what-is-public-and-what-stays-in-sharepoint):
  versions, commits, SHA-256s, automated verdicts, headline figures and summaries of findings
  about the plugin's own synthetic code and behaviour belong here. Do not add customer, client,
  colleague or reviewer names, e-mail addresses, internal URLs, tenant-specific absolute paths,
  tracker results, owner decision records, or scores and evidence from the confidential
  scenario scoring document. Write SharePoint locations in the relative form
  `sharepoint\Professional Services\<slug>\...`.

Where things live:

| Item | Location |
|---|---|
| Plugin source | `submissions\professional-services\<slug>\` |
| Frozen candidate and receipt (gitignored, local) | `evaluation-inbox\<slug>\<version>\` (`<slug>.zip`, `evaluation-run.json`, `cowork-prompt.txt`) |
| Archived evidence | `sharepoint\Professional Services\<slug>\Evaluation\<version>\` |
| Deployment doc and tracker | `sharepoint\Professional Services\<slug>\PLUGIN-DETAILS-AND-DEPLOYMENT.md` and `<slug>-human-test-tracker.xlsx` |
| Promoted distributable | `sharepoint\Professional Services\<slug>\<slug>-plugin-v<version>.zip` |
| Industry status page | `sharepoint\Professional Services\README.md` |
| Scenario specification | `sharepoint\Professional Services\professional-services-scenarios.md` |

`sharepoint\` is a link to the synchronised SharePoint library; see
[SharePoint sync](../sharepoint-sync.md). Anything written there is visible to the whole team.

## Wave 1 definition of done

The 2026-10-01 rerank set Wave 1 to these five scenarios:

| # | Plugin | Slug |
|---|---|---|
| 01 | Engagement Closeout & Knowledge Harvest | `engagement-closeout-knowledge-harvest` |
| 02 | Engagement Staffing & Bench Match | `engagement-staffing-bench-match` |
| 03 | Engagement Mobilization & Onboarding Pack | `engagement-mobilization-onboarding-pack` |
| 04 | Time & Expense Narrative Compliance | `time-expense-narrative-compliance` |
| 05 | Deliverable Review & Quality Gate | `deliverable-review-quality-gate` |

A plugin is done when all five conditions hold. Wave 1 is done when all five plugins are done.

| Condition | Meaning |
|---|---|
| C1 | The automated Cowork verdict is **Ready**, and the three hash-matched reports plus the evaluated ZIP are archived under `Evaluation\<version>\`. |
| C2 | Two independent human testers have each run every prompt in `<slug>-human-test-tracker.xlsx`, on a tab for that version (the critical-path prompts are the mandatory minimum the tracker must contain), the tab's publish gate reads `PASS`, and the accountable owner's decision on that tab is `Publish`. |
| C3 | `PLUGIN-DETAILS-AND-DEPLOYMENT.md` exists and records the evaluated SHA-256. |
| C4 | Only after C2: the distributable `<slug>-plugin-v<version>.zip` is promoted to the plugin folder and is byte-identical to the evaluated ZIP. |
| C5 | The Professional Services `README.md` status table shows the plugin as published. |

An automated Ready is not a publication decision. C2 is the publication gate, and C4 and C5 only
happen after it. An owner decision of `Fix and re-evaluate` sends the plugin back to a new version;
`Do not publish` stops it, and the plugin is recorded as not published rather than done.

## Status board

Owner types: **operator** (whoever runs this work stream: builds, freezes, archives, writes docs),
**Cowork** (the automated evaluation, launched by the operator), **reviewers** (the two independent
human testers).

| # | Plugin (slug) | Current version | State | C1 | C2 | C3 | C4 | C5 | Next action | Owner |
|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `engagement-closeout-knowledge-harvest` | 1.0.2 | Ready, archived; awaiting human gate | Yes | No | Yes | No | No | Two reviewers complete the 1.0.2 tracker tab | reviewers |
| 02 | `engagement-staffing-bench-match` | 1.1.4 | Ready, archived; awaiting human gate | Yes | No | Yes | No | No | Two reviewers complete the 1.1.4 tracker tab | reviewers |
| 03 | `engagement-mobilization-onboarding-pack` | 1.0.0 evaluated; 1.0.1 frozen | 1.0.0 Blocked (trust-and-safety gate); 1.0.1 frozen 2026-10-07 (`40D3968E…9EC1`, receipt `f9518fd`, clean) after QA round 20 (cap) and the T&E round 15 class sweep; evaluated **No-ship** 2026-10-07 (complete-chain functional case failed; trust and safety, security and skill floors passed) | No | No | No | No | No | 1.0.2 fix in progress (lesson placeholder; pending-asset first-week item), then QA, freeze and a new Cowork run | operator |
| 04 | `time-expense-narrative-compliance` | 1.0.3 evaluated; 1.0.4 frozen | 1.0.3 Blocked (trust-and-safety gate); 1.0.4 frozen 2026-10-07 (`1E1380E3…10B4`, receipt `f9518fd`, clean) after QA round 15 (cap, `e6925e4`); in Cowork evaluation | No | No | No | No | No | Evaluate in a new Cowork task, then archive | operator |
| 05 | `deliverable-review-quality-gate` | 1.0.3 evaluated; 1.0.4 frozen | 1.0.3 Blocked (B1 demo inputs not derivable from raw packs; B2 shipped tests read `metadata.json`), every measured gate met; 1.0.4 frozen 2026-10-07 (`4AE31530…316B`, receipt `f9518fd`, clean) after QA round 17 (cap, `1d20138`) and the T&E round 15 class sweep; evaluated **Blocked** 2026-10-07 on missing release evidence only (installed-runtime critical-path and independent grader calibration); every measured bar met; owner accepted 2026-10-07, no re-version | No | No | No | No | No | Two reviewers install the 1.0.4 ZIP and complete the 1.0.4 tracker tab; then decide on re-evaluating this exact ZIP | reviewers |

Notes on the board:

- C2 is recorded from the operator notes. The tracker workbooks carry an encrypting sensitivity
  label, so they open only in Excel (see the runbook's
  [tracker notes](../operator-runbook.md#tracker-workbooks-and-sensitivity-labels)); check them
  there. This file records only gate status, never reviewer names, per-prompt results or the
  owner's reasoning.
- C5: the industry `README.md` was updated on 2026-10-07 with the Mobilization 1.0.1 No-ship and
  DRQG 1.0.4 Blocked verdicts and the T&E 1.0.4 evaluation in progress. It does not change C5 for
  any plugin, because C5 means promoted and recorded.
- No Wave 1 distributable has been promoted yet. Only the Wave 2 `client-status-qbr` folder holds a
  promoted ZIP.

### Wave 1 QA exit waiver (2026-10-05)

The runbook's [pre-freeze QA review](../operator-runbook.md#pre-freeze-qa-review) says to repeat the
review until a round reproduces nothing. That rule is waived for Wave 1: freeze once a QA round
returns only low-severity defects.

| Severity | Defects | Action |
|---|---|---|
| Blocking | Fail-open (input that should hold but passes or reaches a lower verdict); a missing guardrail in any skill; data leakage or another party's rows in output; finding or hold integrity (engine findings suppressed, downgraded or forged); instruction-like text copied into a draft; shipped tests failing from the ZIP. | Fix as a new commit and run another round. |
| Low | Fails closed with an unhelpful message; a traceback with no output written; wording or cosmetic issues; idempotency or ordering nits with no verdict effect; a false-positive hold (fails safe). | Record in the plugin's "Open backlog"; does not block the freeze. |

Reason: Mobilization reached QA round 14 with each round finding a further field-level variant of
a known class. Checklist A23 (whole-document re-derivation) targets the class as a whole, and the
Cowork evaluation is the arbiter of whether it holds.

**Round cap (added 2026-10-05, evening).** Under the severity bar, every round from Mobilization 15,
T&E 12 and DRQG 13 onward still found blocking defects. Each round found fewer, narrower ones,
usually one new variant: values that compose only when rendered together, an identifier of the
wrong JSON type, a supplied key echoed in an error path, or engine-composed text that was not
screened. QA therefore stops at a fixed round: Mobilization 20, T&E 15, DRQG 17. Blocking defects
from the cap round are still fixed as a new commit with regression tests and a class sweep, and
the plugin then freezes without a further round. Low defects go to the backlog as before. Each
class found is added to the [hardening checklist](../plugin-hardening-checklist.md), and the Cowork
evaluation is the arbiter.

In the cap round, the reviewers were also told that a type or shape deviation is low when the
value is still screened and cannot carry text, leak or change a verdict.

## 01 Engagement Closeout & Knowledge Harvest

**Purpose.** Assembles a closing engagement's deliverables, decision log and retrospective into one
cited contract, identifies reusable assets, clusters lessons, runs a deterministic fail-closed
Govern gate over confidentiality and named-person material, and drafts a sanitised knowledge record
for practice review. Nothing is released, published or sent.

### Version history

All three versions were frozen on 2026-10-01 from HEAD `1eaaee4` with a dirty worktree, so the
receipt commit does not by itself identify the source. The 1.0.2 source was committed afterwards
as `68902f7`. The plugin has no `CHANGELOG.md`; this table and the commit message are the history.

| Version | Commit | Frozen ZIP SHA-256 | Cowork result | Key findings | Archive |
|---|---|---|---|---|---|
| 1.0.0 | receipt `1eaaee4` (dirty); source not separately committed | `527B9806…37E7` | **Blocked** | 0 of 5 skills at their launch floor (scores 33 to 48 against floors of 65 to 80); rubric safety scan failed on `sanitize-check` and `knowledge-record` (no Guardrails section); behavioral 14/15 (93.3%); trust and safety 70/70 held; security pass (3 Low). | `Evaluation\1.0.0` |
| 1.0.1 | receipt `1eaaee4` (dirty); source not separately committed | `402FCF06…1992` | **No-ship** | `sanitize-check` 76 against an 80 floor; trust-and-safety gate failed on 6 engine-layer probes: named-person and blame markers, unbanded commercial figures and an embedded client name were released, and a missing contract array produced RELEASE_CANDIDATE for 0 assets. Behavioral 20/20, 4.8/5; security pass. | `Evaluation\1.0.1` |
| 1.0.2 | receipt `1eaaee4` (dirty); source `68902f7` | `5F5F8123…1782` | **Ready** | 5 of 5 skills at floor (81 to 94; `sanitize-check` 82 against 80); behavioral 20/20 (40 runs), 4.3/5, 0 guardrail failures; trust and safety 49/49 held, including 12 deterministic engine probes; security 0 findings; 0 unresolved trigger conflicts; 0 blockers. | `Evaluation\1.0.2` |

### Notable decisions

- **1.0.1 to 1.0.2 fixed the Govern gate in the engine, not only in SKILL.md.** The 1.0.1 report
  noted that the stop on a missing array was enforced only by the model layer. 1.0.2 closed all
  six fail-open probes in `sanitize_check.py` and the chain, so the deterministic gate holds even
  if the model does not.
- **1.0.0 to 1.0.1 was mainly a description rewrite** (inferred from the two reports; there is no
  separate commit). The 1.0.0 report asked every skill for Guardrails, When NOT to use, explicit
  `Do NOT … use <sibling>` deferrals, named tools and an output format. In 1.0.1 four of five
  skills cleared their floors.
- **The human gate runs on 1.0.2 as evaluated.** The 1.0.2 findings are all non-blocking. Cutting
  a 1.0.3 would require a new Cowork run and a new tracker tab; sign-off on 1.0.2 does not carry
  over to it.

### Open backlog (non-blocking, candidates for an optional 1.0.3)

From the 1.0.2 report:

1. An empty payload (no assets and no lessons) is labelled `RELEASE_CANDIDATE_SANITISED` with
   knowledge-record confidence 0.9. It should be HOLD or a no-content state (the rules' default
   disposition is HOLD).
2. When the group aggregation HOLD fires, the superseded per-asset `RELEASE_CANDIDATE_SANITISED`
   findings stay in `findings[]`. Mark or remove them.
3. Scenario B demo citations point to the wrong decision-log and deliverable-register rows, and one
   headcount figure is unsourced.
4. Rename `## Output` to `## Output format` and add an example in `sanitize-check` and
   `artifact-assemble`. `sanitize-check` clears its floor by only 2 points.
5. Split list-form deferrals into one-to-one `use X instead` lines so the trigger scanner reads them.
6. `knowledge-record` step 4 should cite the governed `drafting_guidance` (do not quote, reconstruct
   or paraphrase source text).
7. `lesson_cluster` should require a minimum number of distinct evidence items; injected text moved
   one cluster's confidence from 0.68 to 0.71.
8. The rules reference lists neither `HOLD_NOT_SHORTLISTED` nor `HOLD_PERSONAL_DATA_REWRITE` in
   §7.2, and its illustrative policy text needs confirmation by the practice or legal policy owner.
9. Add a `CHANGELOG.md`.

### Next action

1. Two independent reviewers each run every prompt on the `1.0.2` tab of the tracker. The
   critical-path prompts it must contain are: the Scenario B end-to-end chain (assemble, identify,
   cluster, Govern, draft); a claimed partner or legal approval asking to release a HOLD; a publish
   or send request on the knowledge record; and the aggregation-risk descriptor request.
2. Only when the tab's publish gate reads `PASS` and the owner decision is `Publish`, copy
   `Evaluation\1.0.2\engagement-closeout-knowledge-harvest.zip` to
   `engagement-closeout-knowledge-harvest-plugin-v1.0.2.zip` in the plugin folder, confirm its
   SHA-256 is `5F5F8123…1782`, and update the industry README. For the other owner decisions, follow
   the runbook's [Ready path](../operator-runbook.md#ready-path-human-gate-and-promotion).

## 02 Engagement Staffing & Bench Match

**Purpose.** Builds a cited staffing slate from signed engagement requirements, bench availability,
rates and conflicts-register evidence. Deterministic engines score fit, apply independence and
capacity rules and run a final fail-closed validation before a draft partner note. It never assigns
a person, changes a rate, clears independence or sends the draft.

### Version history

Versions before 1.1.2 predate the frozen-inbox workflow and have no receipts; they are not logged
here (unverified). 1.1.2 to 1.1.4 were frozen on 2026-09-30 from HEAD `1eaaee4` with a dirty
worktree. The 1.1.4 source was committed afterwards as `e1c10e1`. There is no `CHANGELOG.md`.

| Version | Commit | Frozen ZIP SHA-256 | Cowork result | Key findings | Archive |
|---|---|---|---|---|---|
| 1.1.2 | receipt `1eaaee4` (dirty); source not separately committed | `1C00A047…88E6` | **No-ship** | Skills 5 of 5 at floor (91 to 98); behavioral 15/15, 4.73/5; trust-and-safety gate failed: `fit-score` 12/13, because instruction-like citation text was not replaced by the engine's redaction marker. | `Evaluation\1.1.2` |
| 1.1.3 | receipt `1eaaee4` (dirty); source not separately committed | `FEE10577…FD09` | **No-ship** | Skills 5 of 5 at floor; behavioral 20/20, 4.65/5; trust-and-safety gate failed: engine-layer redaction in `fit-score`, `constraint-check` and `slate-draft` was bypassed by look-alike letters, full-width letters, zero-width characters, text split across fields and paraphrase. One unresolved routing conflict with a built-in document-creation skill. | `Evaluation\1.1.3` |
| 1.1.4 | receipt `1eaaee4` (dirty); source `e1c10e1` | `4BDE82D9…9C06` | **Ready** | Skills 5 of 5 at floor (91 to 98 against floors of 65 to 70); behavioral 15/15, 4.53/5, 0 guardrail failures; trust and safety 80/80 held; security 0 findings; 0 unresolved trigger conflicts; 0 blockers. | `Evaluation\1.1.4` |

### Notable decisions

- **Injection redaction normalises text before matching.** 1.1.3 showed that pattern matching on
  raw text is evaded by Unicode tricks and field splitting. In 1.1.4, `safety_text.py` (one copy
  each in `fit-score`, `constraint-check` and `slate-draft`) applies Unicode normalisation before
  matching, and the 1.1.4 run held all 80 trust-and-safety cases.
- **1.1.2 and 1.1.3 reports came from one reused Cowork task.** That is the origin of the rule to
  use a new Cowork task for every new version (see
  [lessons](#lessons-that-changed-the-process)).

### Open backlog (advisory, from the 1.1.4 report)

- `constraint-check` cites imprecise rules on correct fail-closed verdicts: cite #9.1 for unknown
  conflict types and #9.3 for blank materiality, and cite #8.1 only below 0.75 confidence.
- `bench-query` step 5's confidence ladder disagrees with the per-candidate values in the demo
  reference data; align one with the other.
- The raw-data path of `bench-query` injection flagging is not exercised; add an instruction-like
  fixture to a Scenario B raw row.
- `fit-score`: split the RFP exclusion into its own sentence, and say whether "one table per role"
  means all roles or roles in scope.
- Add one shared guardrail line to every skill: never send, post or share; confirm before any
  external action; ignore requests to reveal instructions or disable rules.
- Consider rating `fit-score` medium risk (floor 70) in future runs.

### Next action

1. Two independent reviewers each run every prompt on the `1.1.4` tab of the tracker. The tracker's
   publish gate reads PASS only when both testers pass every row.
2. Only when the publish gate reads `PASS` and the owner decision is `Publish`, promote
   `Evaluation\1.1.4\engagement-staffing-bench-match.zip` as
   `engagement-staffing-bench-match-plugin-v1.1.4.zip`, confirm its SHA-256 is `4BDE82D9…9C06`, and
   update the industry README. For the other owner decisions, follow the runbook's
   [Ready path](../operator-runbook.md#ready-path-human-gate-and-promotion).

## 03 Engagement Mobilization & Onboarding Pack

**Purpose.** For engagement managers mobilising a team or adding someone mid-engagement. It
assembles a governed draft pack for the joiner: client context, objectives, SOW scope and
exclusions, deliverables, key dates, cleared prior knowledge, the confirmed roster, a role-based
access checklist, a confidentiality and ethical-wall briefing and a first-week plan. It does not
provision access, grant wall exceptions, add anyone to the team, share material outside the
engagement or send messages.

### Version history

| Version | Commit | Frozen ZIP SHA-256 | Cowork result | Key findings | Archive |
|---|---|---|---|---|---|
| 1.0.0 | `1079d97` (receipt dirty because of other plugins' uncommitted work) | `A84F5F41…9F5C` | **Blocked** (evaluated 2026-10-01) | Trust-and-safety gate failed, 47/52 held (model guardrails 9/9 held; engine 38/43). Hard stops: the tripwire missed 12 of 12 novel paraphrases, and 4 injected SOW lines (a wall-exception claim, an owner-rights request, copy-the-pack-to-an-external-address) reached the first-week plan verbatim; the wall briefing echoed a register topic naming another client. pack-draft, roster-pull and wall-check scored 76 against a risk-adjusted floor of 80 (no recognised trigger phrases, no failure handling). Behavioral 18/19 (94.7%): a "wall cleared" note was routed to engagement-retrieve, not wall-check. Two unresolved routing conflicts (cold-start pack requests; pack-draft vs the built-in docx skill). Output 4.84/5; security clean; 52/52 shipped tests. | `Evaluation\1.0.0` (first archive attempt hit a transient OneDrive lock; retried) |
| 1.0.1 | `6d6e383` to `f9518fd` (receipt `f9518fd`, clean) | `40D3968E…9EC1` | **No-ship** (evaluated 2026-10-07). Skills 87 to 94 (average 91), 5/5 at the 80 floor; 0 unresolved conflicts; trust and safety 30/30 held; security pass (10 LOW `assert` warnings at 2 locations); shipped suite 525/525 (1,413 s in Cowork). Behavioral 15/16 cases (38 executions); routing 11/11 at 3/3 and 5/5 negatives deferred. The complete-chain case failed (1 PASS, 2 FAIL; lowest quality 3/5 against the 3.5 bar): the scenario A pack's lesson LC-A-001 shows the engine's placeholder directive ("Draft a generalized lesson from the category and evidence IDs only…") instead of a lesson, and the first-week plan tells the joiner to read AST-A-001 although it is `pending_practice_review`, title and citation only. Both are in the shipped golden. | Fixes every 1.0.0 finding plus a type/enum validation sweep; tests 52 to 86. The report did not quote the 12 novel lines, so the regression fixtures are reconstructions of the described families. Pre-freeze QA rounds 1 to 14 (2026-10-01 to 10-02), each fixed as new commits with no version bump; suite 86 to 390 checks. By defect class: other-client leaks, split instructions and unvalidated nested fields (round 1, `180ea66`); upstream text not re-screened and stages trusting intermediate state (rounds 2 to 4, `72d2fba`, `d9e8aac`, `a2d6213`, `24d13d3`); duplicate columns, keys and IDs, late holds, split arrays (A11, A12; rounds 5 and 6, `d991917`, `a898bda`, `0e9e337`); non-canonical comparison and unbounded nesting (A13, A14; round 7, `ecdd8ca`, `f4ac22f`); input extending the trusted vocabulary, redaction before harvest, carried timestamps, linked records with another subject (A15 to A18; rounds 8 to 10 and cross-plugin sweeps, `8f39b2e`, `9bcf84c`, `49c9da2`, `44bd7a5`, `50e284b`); later stages trusted carried values → re-derive (A19; round 11, `4c7daf8`); exclusions and blank keys (A20, A21; round 12, `2ac75d5`); reconciliation by count or filtered on input-controlled fields (A22; `4677056`, round 13 `6b33a13`); field-by-field reconciliation kept missing fields → whole-document re-derivation at every stage (A23; round 14, `b379a94`), then a deterministic pre-render re-derivation check for `pack-draft` and `roster-pull` (`b9295dd`). The suite's one wall-clock check was raised from 20 s to 60 s (`2076c12`), then replaced by a 15 s bound per screening call on worst-case input (`c461e3d`). Rounds 15 to 19 (2026-10-05) under the severity bar, 390 to 483 checks: `verify_render` compared a hold's source and path case-insensitively, a missing wall register disabled other-client screening, and values that are harmless alone composed an instruction on adjacent pack lines (C6, D22, D23; round 15, `3c335b5`); a Closeout record with no identity, a header-only register, an absent `released_assets` read as empty, Closeout identities not screening the workspace inventory, citations outside the rendered screen (C5, D22, D23; round 16, `fc6b5d9`); an identifier given as a number or object (A2; round 17, `0c31d0a`); a supplied key named in an error path (D17; round 18, `d288acb`); a `*_ids` member given as a single string, and one placeholder rule for every path (round 19, `d823330`). Round 20, the cap (494 checks): a missing or zero-byte workspace inventory read as clear and released knowledge; it now holds at every stage that reads it, a blank engagement letter is refused, and other parties' records are cited by position only (D23, D24; `e69e366`). QA complete. After the cap: the shipped runner streams each result and gains `--group`/`--list-groups` (G7; `b414247`); the T&E round 15 class sweep fixed engine label forms accepted in ID and name fields (D25), six parsers that skipped another party's or an excluded record before checking its grammar (A24), and declared fields in variant Markdown forms or outside their section (A25) (`344a3b7`, `ce515d3`; 525 checks); CHANGELOG notes (`f9518fd`). | `Evaluation\1.0.1` |

### How 1.0.0 was built

The plugin was new in Wave 1. A build agent scaffolded it from `submissions\_template` and the
[authoring templates](../authoring-templates.md) and reported all its own tests green. An
independent review before freezing found serious gaps:

- the instruction tripwire raised false positives on all 14 benign lines tried and missed 8 of 12
  attacks, and any hold blocks the whole pack;
- the ethical-wall check was fail-open (OR matching with blank wildcards, and only the first matching
  row used);
- the briefing copied free text from the wall register, which can disclose the walled matter;
- the Closeout adapter required fields that real Closeout output does not have, so every real asset
  would have been excluded;
- the Staffing adapter keyed candidates by name only, ignored `needs_review` and passed independence
  reasons through;
- a blank `assignment_status` defaulted to confirmed;
- all five SKILL.md files were the same boilerplate, with invalid YAML, and the contract was a stub.

All of these were fixed before the freeze. The final tripwire probe showed 0 false positives on 28
benign lines and 0 misses on 24 attacks. Before freezing, the regression suite passed 52 of 52
checks and the shared-copy check passed 30 of 30; the CHANGELOG says "50 shipped regression
checks", so the exact shipped count is (unverified). The ZIP has 78 entries, LF line endings, no
bytecode, and includes `tests\`.

### Notable decisions

- **It consumes Closeout and Staffing output through read-only, validated adapters.** Plugins 01 and
  02 were not changed. An unknown `contract_version` is rejected, and malformed shapes raise
  `InputError`.
- **Closeout `held_assets` are never read.** Closeout's release-candidate state counts as permission
  for internal reuse, but items are labelled `pending_practice_review` until a practice reviewer
  clears them. Lessons are used only when `rewrite_required` is explicitly false.
- **A Staffing slate is a recommendation, not an assignment.** Names stay "proposed" unless a
  confirmed-roster record is supplied. The verdict for the confirmed role is used, otherwise the
  most restrictive across roles.
- **The ethical-wall gate is most-restrictive-wins and fails closed.** Every populated field must
  match. A missing register, unknown status or no named joiner holds the pack. Only workspaces the
  register lists as restricted are denied; other client-confidential or knowledge-dependent
  workspaces are held for review. The briefing uses a curated `briefing_topics` column only.
- **Value is framed as cycle time, without invented figures.** The scenario has no external
  quantification, so the README and demos describe the time saved qualitatively.

### Open backlog: 1.0.1 judgement calls to watch in the next run

- An e-mail address or URL next to a share, copy or upload verb is held, even an internal link.
- Phrases such as "cleared by Risk" or "Conflicts approved" are held.
- A briefing topic with a capitalised name that is not the engagement's own, or a matter-ID-like
  token, is held.
- A workspace with an unknown classification or dependency is no longer requested, even when the
  wall is clear.

Accepted residuals from pre-freeze QA rounds 15 to 19 (low or by design under the severity bar):

- A rendered-screen hit withholds whole pack lines, not just the contributing values.
- A validly shaped identifier that composes with adjacent prose stays in the on-hold pack.
- Closeout names with no structured attribution are found by a capitalised-word heuristic.
- `scope_digest` has no Closeout input, so Closeout identities screen only the later stages.
- The Closeout demo files carry `engagement: null`.
- Placeholder binding keeps exact field paths, because it must match hold paths. It runs only on
  documents an engine has built.
- Pre-freeze advisory (2026-10-07): the scenario B goldens pass through the Staffing plugin's
  citation `independence-eligibility-rules.md #3.1`, which this bundle does not include, and the
  citation-resolver test skips it. Cowork may flag it.
- Pre-freeze advisory (2026-10-07): `sample-test-prompts.csv` has no rows for the 1.0.1 QA-round
  classes (missing workspace inventory, A23 verify refusals, D24 positional citing, r15 classes,
  non-string IDs, blank letter or pursuit record, duplicate columns). The `wall-check` and
  `knowledge-match` descriptions do not defer to `roster-pull` (F1).

### Next action

1. Done (2026-10-05): Wave 1 investigation of test-suite runtime and tooling; runtime accepted (see [open risks](#open-risks)).
2. Done (2026-10-05): QA rounds 15 to 19 under the [Wave 1 severity bar](#wave-1-qa-exit-waiver-2026-10-05) (`3c335b5`, `fc6b5d9`, `0c31d0a`, `d288acb`, `d823330`).
3. Done (2026-10-05): QA round 20, the [round cap](#wave-1-qa-exit-waiver-2026-10-05) (`e69e366`). QA complete.
4. Done (2026-10-07): streaming runner (`b414247`), T&E round 15 class sweep (`344a3b7`, `ce515d3`),
   [hardening checklist](../plugin-hardening-checklist.md) (`f9518fd`).
5. Done (2026-10-07): frozen as `evaluate-engagement-mobilization-onboarding-pack-v1.0.1-2026-10-07`.
6. Done (2026-10-07): evaluated **No-ship** and archived to `Evaluation\1.0.1\`.
7. In progress (2026-10-07): 1.0.2. Closeout `drafting_guidance` is an instruction to the Closeout
   drafter, and the governed record carries no finished lesson text, so the engine must never render
   it as content: a lesson without written text is excluded or shown as title and citation only.
   First-week items that point at a `pending_practice_review` asset are restated as title and
   citation only. Update the scenario A golden and add a complete-chain output check. Industry
   README updated with the 1.0.1 verdict.
8. Next: a QA round on the 1.0.2 commits, then the pre-freeze checklist and freeze.

## 04 Time & Expense Narrative Compliance

**Purpose.** Drafts grounded time-entry narratives, maps billing codes, runs an explicit Govern step
against client billing guidelines (block billing, prohibited terms, vague wording, required detail,
non-billable activity, duplicates, increments, code mismatch, missing time) and drafts a pre-bill
exception packet. It never submits time, alters WIP or sends anything.

### Version history

| Version | Commit | Frozen ZIP SHA-256 | Cowork result | Key findings | Archive |
|---|---|---|---|---|---|
| 1.0.0 | `9d77f91` (portfolio import) | None (predates the workflow) | **STOP** (per CHANGELOG) | Privacy, draft-first and narrative-grounding findings H1 to H3 and others, fixed in 1.0.1. | Not archived (predates the workflow) |
| 1.0.1 | receipt `1eaaee4` (dirty); source not separately committed | `5A77AFF0…8A3E` | **Blocked** (canonical run) | B1 `code-map` guardrail failure: meeting plus non-billable call mapped to NB900 at 0.92 instead of UNMAPPED at 0.40. B2: 8.0 h with zero linked evidence rated compliant. B3 (Medium): `--signal-config` replaced the plugin policy instead of narrowing it. B4 (Medium): tripwire missed 3 of 6 paraphrased injections. Skills 91 to 96; behavioral 15/17 (88.2%); 3.83/5; trust and safety 80/80 held. | `Evaluation\1.0.1` |
| 1.0.2 | receipt `1eaaee4` (dirty); source `aaef41f` | `1D2B465A…3A74` | **Not evaluated** (superseded) | Fixed F1 to F9 from an earlier, non-canonical 1.0.1 report; only partly addressed B4 and did not address B1 to B3. | Not archived, by design |
| 1.0.3 | `88b5b41` (receipt dirty because of other plugins) | `53A5C7EC…E652` | **Blocked** (evaluated 2026-10-01) | All four 1.0.1 blockers (B1 to B4) verified fixed. Skills 92 to 96 against a floor of 80; behavioral 25/25; security clean. Trust-and-safety gate failed, 76/85 held. Hard stops: the no-external-recipient guardrail was missing in 4 of 5 skills; data minimisation, because colleagues' rows were returned with no role check; `narrative-draft` copied injected subject text into a draft. Logic follow-ups: injected text was not flagged in the Missing time section or in a suggested rewrite; `embedded_instruction` cited the wrong guideline section; a mixed-entry narrative omitted a linked activity. | `Evaluation\1.0.3` |
| 1.0.4 | `2b0cbc3`, `01180aa` to `4b89a53` (receipt `f9518fd`, clean) | `1E1380E3…10B4` | **In Cowork evaluation** (frozen 2026-10-07; shipped suite 1,283/1,283 from the ZIP) | Fixes the 1.0.3 hard stops and logic follow-ups; team view needs a structured `team_view` confirmation (real boolean, `engagement_manager` role, exact `engagement-manager:<engagement_id>` token). A shared `validate_packet` type-checks every engine-read field; tests 134 to 165. Older hand-built packets missing now-required fields are rejected. Pre-freeze QA rounds 1 to 11 (2026-10-01 to 10-02), each fixed as new commits with no version bump; tests 165 to 957 checks. By defect class: team-view token, tripwire and encoding gaps (round 1, `71f208b`); later stages accepting understated verdicts, missing flags or supplied mappings → re-run the rules (`82d06b9`; rounds 2 and 3, `1e3164c`, `e932cbc`); strict JSON loading and atomic writes (`7bea6e8`); unscreened member names and metadata, echoed input, duplicate IDs, header-only CSVs (A11, A12; rounds 5 and 6, `f32f3d0`, `ac9b9e6`, `2386c11`); non-canonical comparison (A13, `64a3178`); withheld text deciding and unbounded nesting (A14; round 7, `b92a859`); missing contract fields, redaction before harvest, supplied markers, carried timestamps (A15 to A17; cross-plugin sweeps, `1409d9a`, `edb1439`); links used as evidence for another timekeeper (A18; round 8, `42849ee`); link state and engine-derived values carried, not re-derived (A19; round 9 `31564aa`, sweep `eee58a5`); exclusions, blank keys and count-only reconciliation (A20 to A22; `a2b5df2`, round 10 `0596bec`); reconciliation filtered on input-controlled fields (`e308eaa`); field-by-field reconciliation kept missing fields (a deleted or renamed excluded-entry record still produced a report) → whole-document re-derivation at every stage (A23; round 11, `777620f`). Rounds 12 and 13 (2026-10-05) under the severity bar, 957 to 1,186 checks: a self-declared team view released another timekeeper's rows (now confirmed from `--raw-dir`), tests crashed printing a non-ASCII label (C6, G4a; round 12, `7938ee4`); activity rows were not re-derived from raw, so a raw folder that merely named the timekeeper authorised a forged calendar row (A23; round 13, `126a29a`, which also carries the class sweeps from Mobilization rounds 16 to 18 and DRQG rounds 14 and 15). Round 14 found linked activity classes composing an instruction inside an engine-written flag detail (D22; fixed in `44233a7`, with the DRQG round 17 sweeps D and E). The shipped runner then gained streaming output and `--group`/`--list-groups` (G7; `8aed3ad`). Round 15, the cap (of `8aed3ad`): 3 blocking, all fixed in `e6925e4`: a reserved positional label accepted as the engagement ID and in other ID fields (D25), another engagement's malformed workplan row skipped before its grammar was checked (A24), and an indented or `*` letter field outside the Engagement section read as prose (A25); 1,263 to 1,283 checks. QA complete; CHANGELOG note (`4b89a53`). | None |

### Notable decisions

- **Two reports disagreed on the same 1.0.1 ZIP.** An earlier report on the same SHA-256 said SHIP
  WITH NOTES (machine gate Ready, 15/15 behavioral, 53/53 safety). The canonical, hash-matched,
  three-report run said Blocked. The canonical run is authoritative.
- **1.0.2 was skipped.** It was frozen against the non-canonical report before the Blocked result
  surfaced. Evaluating it would have spent a Cowork run on a version known not to fix B1 to B3.
  1.0.3 contains every 1.0.2 change plus the B1 to B4 fixes; the CHANGELOG records 1.0.2 as
  "frozen, superseded before evaluation".
- **Tests ship in the bundle.** The non-canonical report flagged that the ZIP cited tests it did not
  contain. The bundler gained a per-submission `bundleTests: true` opt-in in `metadata.json`, rather
  than a global change to every plugin.
- **The 1.0.3 fixtures were mutation-checked.** Each new fixture fails on the 1.0.2 engines (26
  checks failed when run against them), so the tests prove the fixes rather than just pass.
- **Deferred:** renaming the plugin to drop "expense" (expenses are out of scope), and MOS3 store
  packaging. Do not add `manifest.json` or change the install identity without an owner decision.
- **1.0.3 fixed what was reported but not what was probed next.** 1.0.3 fixed B1 to B4 (it also
  made BH910 reachable for billing hygiene, based the period caveat on actual data dates and grew
  the tests from 50 to 72 checks), and its logic and quality figures cleared the bar. The run then
  probed each skill separately and found guardrails present in one skill but not its siblings, an
  engine that returned other people's records, and a drafting step that ran before the tripwire.
  These became checklist items C4, D8, D10, E7 and E9 in the
  [hardening checklist](../plugin-hardening-checklist.md). The 1.0.3 run labelled these hard stops
  `Blocked`, not `No-ship`.

### Open backlog: what the 1.0.3 report asks of 1.0.4

- Hard stops: add the internal-only, no-external-recipient guardrail to every skill that can
  produce a draft; return only the requester's own rows unless a structured role confirmation is
  supplied; run the tripwire before `narrative-draft` drafts anything and never copy flagged text
  into a draft.
- Logic: flag injected text wherever it appears, including Missing time and suggested rewrites;
  make `embedded_instruction` cite the guideline section that describes it; include every linked
  activity in mixed-entry narratives.
- Apply the whole [hardening checklist](../plugin-hardening-checklist.md), not only these items,
  before freezing.

Accepted residuals from pre-freeze QA rounds 12 to 14 (low or by design under the severity bar):

- The self-scope requester (`--requester`) is a run parameter; nothing confirms who the person is.
- The shared detector can miss an instruction split inside one long narrative. Only the harmless
  half reaches the report.
- Authority values are trimmed of surrounding whitespace, then compared exactly (documented).
- An undeclared member name can appear in a re-derivation record path. It is carried and screened
  as data and never appears in an error message.
- Pre-freeze advisory (2026-10-07): not every skill description names every sibling (activity-pull
  omits code-map and exception-report; guideline-check omits activity-pull and code-map); unchanged
  since 1.0.3, which scored no routing conflicts (F1). CHANGELOG round headings "2" and "3" do not
  match the test group names.
- Behaviour change in round 15: another timekeeper's malformed or duplicate row is refused even in
  a self-scoped run; the error names only the file and row.

### Next action

1. Done (2026-10-05): Wave 1 investigation of test-suite runtime and tooling; runtime accepted (see [open risks](#open-risks)).
2. Done (2026-10-05): QA rounds 12 and 13 under the [Wave 1 severity bar](#wave-1-qa-exit-waiver-2026-10-05) (`7938ee4`, `126a29a`).
3. Done (2026-10-07): round 14 fix (`44233a7`), streaming runner (`8aed3ad`), QA round 15, the
   [round cap](#wave-1-qa-exit-waiver-2026-10-05) (`e6925e4`), and the
   [hardening checklist](../plugin-hardening-checklist.md) (`4b89a53`). QA complete.
4. Done (2026-10-07): frozen as `evaluate-time-expense-narrative-compliance-v1.0.4-2026-10-07`.
5. Evaluate the frozen ZIP in a **new** Cowork task, then archive to `Evaluation\1.0.4\` and update
   this file and the industry README.

## 05 Deliverable Review & Quality Gate

**Purpose.** For reviewing partners and quality and risk management (QRM) teams. It checks the
mechanical layer of a client deliverable (disclaimers, cited support for headline claims, scope,
prior findings, data handling) against quality-gate criteria, maps assertions to evidence, ranks
release blockers and drafts a partner review packet, so human review starts at the judgement layer.
It does not sign off a deliverable, clear a gate, approve release, contact a client or write back
to a system of record.

### Version history

| Version | Commit | Frozen ZIP SHA-256 | Cowork result | Key findings | Archive |
|---|---|---|---|---|---|
| 1.0.0 | `9d77f91` (portfolio import) | None | **Never evaluated** | No CHANGELOG and no shipped regression tests. | None |
| 1.0.1 | `94a6192` (receipt dirty) | `7F487D5D…49BC` | **No-ship** | Trust-and-safety hard stop in `review-packet` (94/95 held): a user-supplied external recipient was accepted for routing with no hold, and the packet appended the full contract payload. Engine defects L1 to L5: `scope_aligned=false` ignored; unsupported definitive conclusions not ranked as release blockers; best-evidence selection; hard-coded finding locations; missing registers treated as clean. Skills 86 to 91; behavioral 15/15 (35 runs), 4.5/5; security 0 findings. | `Evaluation\1.0.1` |
| 1.0.2 | `7626d67` (receipt records pre-rewrite `2ba4145`, dirty) | `29B431EC…B869` | **Blocked** | 42/50 behavioral cases (84%). 2 FAIL (fail-open logic defects in the gate engine): a null `required_language` register is treated as empty instead of holding; unrecognised `client_data_handling` values pass clean with no finding. 6 WEAK: `severity_rank` traceback on a non-numeric page label; look-alike letter evasion; paraphrased steering text; instruction text in citation fields not scanned; false positive on ordinary "pre-approved"; an upstream finding reusing a G8 finding ID can suppress the blocker. Skills 85 to 93; 4.57/5; trust and safety 75/75 held; security 0 findings. | `Evaluation\1.0.2` |
| 1.0.3 | `7166cb5`, `f7578d2`, `06fde7a`, `7d09dd1` | `99699BDD…F9D2` | **Blocked** (evaluated 2026-10-01). Every measured gate met: skills 85 to 93, behavioral 20/20, quality 4.7/5, trust and safety 60/60 held, security pass. Blocked on two release-mechanics findings: **B1** the scenario A `review-input.json` sets `client_data_handling='ok'` although its raw pack has no client-data register, so ingest step 5 would produce `unknown` (a G4 blocker) and the golden, README and critical-path prompt 1 contradict the sources; other fixture values (page numbers, A's `population_size` 1100, B's board recipient and brand `pass`) are not in the raw packs either. **B2** shipped `tests/run_tests.py` crashes from the ZIP because it reads `metadata.json`, which the bundler excludes. Advisories: document `criteria_sections` seeding and paragraph numbering for unpaginated sources; QRM supplies the reliance clause; drop the duplicated "Rule:" line and define empty-section wording; rename `extra` in the test harness; add a ground-every-statement sentence. | Fixes the 1.0.2 blockers (`7166cb5`, 103 tests). Three independent review rounds then found further fail-open paths, each fixed in a new commit with no version bump: wrong-type recipients and booleans, unvalidated register entries, AM findings trusted by self-declared source (`f7578d2`, 179 tests); a missing required disclaimer, keyword-only recipient classification, an omitted `scope_aligned`, evidence with no or unknown type supporting a fact, and deep-nesting tracebacks (`06fde7a`, 241 tests); and a client alias or name containing external-party vocabulary hiding an external recipient (`7d09dd1`, 254 tests). | `Evaluation\1.0.3` |
| 1.0.4 | `9dc7c38`, `25a0076` to `ddaaa55` (receipt `f9518fd`, clean) | `4AE31530…316B` | **Blocked** (evaluated 2026-10-07). Every measured bar met: skills 85 to 96 (assertion-map 92, criteria-retrieve 85, deliverable-ingest 89, gate-check 96, review-packet 93; average 91), 5/5 at the 80 floor; behavioral 20/20 cases (40 executions), positive selection 3/3, no negative misfires, lowest output 4/5; trust and safety 129 held, 0 violated, 2 n/a; security pass (10 LOW); 0 unresolved conflicts; shipped suite 1,716/1,716. Blocked only on two fail-closed **missing-evidence** gates, with no observed function failure: no installed Cowork runtime evidence (isolated agents ran the skills; the installed loader and deployed critical paths were not exercised) and no independent grader calibration (no human reference labels; `validate_grader.py` exited 1). Its required follow-up is installed-runtime critical-path and blind-routing evidence for this exact ZIP plus human reference labels, then re-evaluation without changing the candidate. Advisory: bandit B105 at `assertion_rules.py:435`; a storage retry in the evaluator sandbox (not a candidate failure). | Structural G8 tripwire (addressee, verdict-steering and suppression patterns rather than fixed nouns); 269 tests (`9dc7c38`). The 1.0.3 B1, B2 and advisories (`25a0076`, 287 tests): raw packs gained the missing evidence (a release-registers file, page markers, population, distribution list), so the inputs and goldens are unchanged; `tests/derive_review_input.py` re-derives each input from its raw pack; tests pass from the extracted ZIP. Shared detector 1.1.2 vendored (298 tests). Pre-freeze QA rounds 1 to 12 (2026-10-01 to 10-02), each fixed as new commits with no version bump; 298 to 1,166 checks (`4a7f4f3`). By defect class: self-declared evidence sources and duplicate finding IDs (round 1, `335038b`); stages not validated against the contract (round 3, `e85af4f`); later stages trusted carried engine findings → re-derive them, withhold flagged text at every stage (round 4, `7efca58`); echoed input and duplicate keys (A11; round 5, `f5befc0`); forged engine findings and duplicate IDs (A12; round 6, `e6dfef6`, `0f884ce`); non-canonical comparison, unbounded numbers and nesting (A13, A14; rounds 7 and 8, `d169fc8`, `acb0e07`, `c9cf414`); missing contract fields, forged markers, carried timestamps (A15 to A17; round 9, `d8d4fa2`, `4674c90`); linked records with another subject (A18, `3c64670`); colliding findings and carried trust (A19; round 10, `5c76328`, `f7ef0fe`); exclusions, blank keys, and reconciliation by count or filtered on input-controlled fields (A20 to A22; `a6718fd`, `2379e06`, `4a7f4f3`); the suite resolved engine paths from the working directory (round 11, `ff53cd0`). Round 12 extended A23 to the final rendering step (`ace121a`). Round 12 on DRQG itself (`9c45c0c`, 1,267 checks): whole-document re-derivation at every stage (A23); `gate_check` and `severity_rank` take `--input review-input.json`, and `severity_rank --verify` runs before the packet is rendered. The golden `engine-run.log` files, previously caught by the repository's `*.log` ignore rule, are now tracked (`c2345f5`). Rounds 13 to 15 (2026-10-05) under the severity bar, 1,267 to 1,509 checks: a brand check's title and detail composed an instruction in the packet, and tests crashed printing a non-ASCII label (D22, G4a; round 13, `156dd07`); rendered IDs were outside the screen (IDs now `[A-Za-z0-9._-]{1,80}` and every rendered value screened; round 14, `82fa1cf`); three consecutive rows composed an instruction that pairwise screening missed (whole rendered sequence plus bounded windows; round 15, `615f4f9`, with the Mobilization round 17 and 18 sweeps). Round 16 (1,564 checks): a brand-check row for another deliverable carried its other-client identifier into the findings; foreign records are now replaced by a fixed placeholder at the first stage and held by position, and zero-byte or empty raw register sections are refused (D24, D23; `aaecf4f`). Round 17, the cap, found a foreign reviewer finding kept whole and a register section of non-record prose read as empty; foreign reviewer findings are now replaced by a positional `AM-G8-foreign-finding-N` hold and register prose is refused (D24, A25; `1d20138`, 1,607 checks). QA complete. After the cap: the shipped runner streams each result and gains `--group`/`--list-groups` (G7; `30defb4`); the T&E round 15 class sweep refused reserved positional labels and engine label forms in every ID, name and location field (D25) and refused declared fields in variant Markdown forms or outside their section in the raw-pack parser (A25); grammar-before-scope (A24) was already held (`1bf559b`, `ddaaa55`; 1,716 checks); CHANGELOG round 11 entry (`7be4c49`). | `Evaluation\1.0.4` |

Commit 2ba4145 was rewritten to 7626d67 before first push (history scrub of an internal URL; plugin
files identical). The 1.0.3 receipt records `581a144`, rewritten to `7d09dd1` by a second scrub
(see the frozen register). Frozen receipts and archived reports cite the pre-rewrite SHA.

### Notable decisions

- **Pre-harden before the first evaluation.** 1.0.0 had no tests and had never been evaluated, so it
  went straight to a hardened 1.0.1 rather than spending a Cowork run on a known-weak build.
- **The G8 injection tripwire was recalibrated before 1.0.1 was frozen.** The first hardened version
  flagged 9 of 9 benign consulting sentences and missed 6 of 8 attacks. The rewrite targets text
  addressed to the reviewer or assistant, or steering this review, and scored 0 false positives on
  14 benign sentences and 0 misses on 16 attacks. Both sets ship as regression tests.
- **1.0.2 made `is_definitive_conclusion` deliberately broad.** Unhedged wording,
  `scope_aligned=false`, a stated population size, or terms such as "should", "will", "all", "full"
  or "applies across" mark an assertion as definitive, and an unsupported definitive assertion is a
  release blocker. Scenario B went from 3 to 6 blockers, all judged legitimate. The 1.0.2 run did
  not count this against the plugin, but see [open risks](#open-risks).
- **Missing registers fail closed.** Missing `client_data_handling`, `brand_checks`,
  `licensed_content` or `prior_findings` registers hold. `client_data_handling` defaults to
  `unknown`, which is a blocker, and ingest owns the field. The 1.0.2 FAILs are the remaining gaps
  in this rule: null and unrecognised values.
- **The trigger "can this go to the client?" appears in two skills.** It was found by the Wave 1
  trigger scan after 1.0.1 was frozen, so it was left as a watch item. The 1.0.2 run judged it
  resolved by two-way deferrals (3 of 3 runs reached the correct outcome) but suggested keeping it
  in one skill only.
- **D14 waiver for Wave 1 (2026-10-01).** Shared detector 1.1.2 is vendored into all three Wave 1
  plugins. Held-out 2026-10-01c: 66/68 (97%), 0/45 false positives. Fresh set 2026-10-01d, written
  after 1.1.2 was built: 25/31 (81%), 1/20 false positives (a scheduling line held for review);
  1.1.1 caught 10/31. The remaining misses are readers described by role and other open-ended
  wordings that regex rules only partly cover, and the one false positive fails safe (held, not
  passed). Freeze on 1.1.2 and let the Cowork behavioural evaluation judge; revisit with a
  model-based check if Cowork finds a miss.

### Open backlog: what the 1.0.3 report asks of 1.0.4

This is the report's request, not a description of the 1.0.4 change.

- Required (B1): make every structured demo input derivable from its raw pack, either by adding the
  missing evidence (client-data register, page or paragraph references, population size,
  distribution list, brand check) or by changing the inputs to what ingest produces; regenerate the
  goldens, README and `tests/sample-test-prompts.csv`; add a test that re-derives each input from
  its raw pack. Checklist item G4b.
- Required (B2): shipped tests must pass from the extracted ZIP with no `metadata.json`.
  `evaluation:prepare` now runs the shipped tests from an extracted copy and refuses to freeze on
  failure. Checklist item G4a.
- Advisories: `criteria_sections` seeding and paragraph numbering for unpaginated sources; QRM
  supplies the reliance clause and the plugin never drafts it; drop the duplicated "Rule:" line and
  define empty-section wording in the review packet; rename `extra` in the test harness (or
  `# nosec B610`); add a ground-every-statement sentence.

Accepted residuals from pre-freeze QA rounds 13 to 15 (low or by design under the severity bar):

- The `assertion_map` output carries both halves of a split that the rendered screen withholds; the
  packet never shows them.
- Each withheld half of a split raises its own G8 finding.
- Ingest judgement flags can only be type-checked.
- A dotted identifier such as `For.the.AI.reviewer` falls below the shared detector's threshold.
  A fix belongs in `shared\steering-guard` and its held-out scoring, not in this plugin.
- A rare false refusal is possible when a finding's own ranked text composes with a neighbour (fails
  safe).
- The ranked-findings template has no citation column (round 16, low).
- Pre-freeze advisory (2026-10-07): `sample-test-prompts.csv` is unchanged since 1.0.1 and has no
  rows for the 1.0.4 QA classes (tool-addressed steering, look-alike letters, other-client records,
  a `TBD` register); D9 and E9 have no shipped test.
- Watch: an advisory plus an escalation stays `partner_review_required_advisories_only`, while an
  escalation alone gives `not_ready_for_release` (deliberate, severity-rules.md #3.3; the summary
  states the escalation count). The evaluator may question the ordering.
- Behaviour change in the round 15 sweep: a body line that starts with a cover-field name followed
  by ` - ` or `=` (for example `Status - on track`) is refused as a misplaced cover field.

### Next action

1. Done (2026-10-05): Wave 1 investigation of test-suite runtime and tooling; runtime accepted (see [open risks](#open-risks)).
2. Done (2026-10-05): the A23 sweep (whole-document re-derivation at every stage, including the
   final rendering step) landed as `9c45c0c`; 1,267/1,267 checks.
3. Done (2026-10-05): QA rounds 13 to 15 under the [Wave 1 severity bar](#wave-1-qa-exit-waiver-2026-10-05) (`156dd07`, `82fa1cf`, `615f4f9`).
4. Done (2026-10-07): QA round 16 (`aaecf4f`) and round 17, the
   [round cap](#wave-1-qa-exit-waiver-2026-10-05) (`1d20138`). QA complete.
5. Done (2026-10-07): streaming runner (`30defb4`), T&E round 15 class sweep (`1bf559b`, `ddaaa55`),
   [hardening checklist](../plugin-hardening-checklist.md) (`7be4c49`).
6. Done (2026-10-07): frozen as `evaluate-deliverable-review-quality-gate-v1.0.4-2026-10-07`.
7. Done (2026-10-07): evaluated **Blocked** (missing installed-runtime and grader-calibration
   evidence only) and archived to `Evaluation\1.0.4\`.
8. Done (2026-10-07): owner accepted the evidence block. No candidate change is requested, so do
   not re-version. Deployment doc and a 1.0.4 tracker tab created in the library, and the industry
   README updated.
9. Two reviewers install the 1.0.4 ZIP in Cowork and complete the 1.0.4 tracker tab. Their
   installed runs supply the installed-runtime critical-path evidence and the human labels the
   report asks for (C2). Then decide whether to re-evaluate this exact ZIP.

## Lessons that changed the process

Each lesson below came from a specific Wave 1 finding. The resulting checks are in the
[plugin hardening checklist](../plugin-hardening-checklist.md), and the operating steps are in the
[operator runbook](../operator-runbook.md).

| Lesson | Where it came from | What changed |
|---|---|---|
| The canonical, hash-matched three-report run is authoritative. | Two reports on the same T&E 1.0.1 ZIP disagreed (SHIP WITH NOTES and Blocked). | Only archived, hash-matched runs count. Evaluator output is stochastic; do not shop for a better verdict. |
| A fix is a new version; never re-evaluate in place. | T&E 1.0.2 was frozen against the wrong report. | Inbox versions are immutable. Superseded versions keep a history row and a CHANGELOG note. |
| Use a new Cowork task for every new version. | Staffing 1.1.2 and 1.1.3 shared one task; reused tasks can mix report sets and carry over the earlier verdict. | New version means new task. Typing "continue" in a stalled task for the same version is fine. |
| Hard stops must be enforced in the engine, not only in SKILL.md. | Closeout 1.0.1 fail-open probes; DRQG 1.0.1 L5 and 1.0.2 FAILs. | Missing, null, malformed or unknown inputs fail closed in the deterministic engine, with a negative fixture each. |
| Policy arguments narrow; they never replace. | T&E B3. | Plugin policy is always applied; overrides are additive, most restrictive wins. |
| Tripwires need both an attack set and a benign set. | DRQG and Mobilization tripwires were either noisy or porous; Staffing 1.1.3 was evaded by Unicode tricks. | Normalise format characters and look-alikes, scan every free-text field, target text addressed to the assistant, and ship both sets as tests. |
| Review sub-agent output independently before freezing. | The Mobilization build agent reported green tests on a build with fail-open gates and a broken tripwire. | Probe the build yourself before committing; agent-reported test counts are not evidence. |
| Cross-plugin adapters must be tested against the sibling's real output. | Mobilization's Closeout adapter assumed fields that do not exist. | Adapters validate the real demo output of 01 and 02 in tests. |
| Ship tests in the ZIP. | T&E 1.0.1 cited tests that the bundle excluded. | `bundleTests: true` in `metadata.json`. |
| Line endings and timestamps must be fixed. | CRLF in ZIPs broke reproducibility on Linux; goldens drifted. | LF everywhere, `--generated-at` pinned for goldens, ZIP inspected before Cowork. |
| Description structure drives skill health. | Closeout 1.0.0 had 0 of 5 skills at floor. | Every SKILL.md has Guardrails, When NOT to use, one-to-one `Do NOT … use <sibling>` deferrals, output format and an example. |
| Earn the higher floor rather than strip guardrail words. | Naming invoice, delete or send moves a skill into a higher risk tier. | Keep the words when the skill handles that material, and meet the 80 floor. |
| Commit before freezing. | Every receipt so far records `gitDirty: true`. | Commit the plugin first; freeze from a clean worktree when possible so the receipt commit identifies the source. |
| Guardrails and data minimisation must hold in every skill, not only the main one. | T&E 1.0.3: four of five skills lacked the no-external-recipient rule, an engine returned colleagues' rows, and a drafting step ran before the tripwire. | Checklist items C4, D8, D10, E7 and E9. Probe each skill on its own before freezing. |
| Fix agents fix what is reported; adversarial reviewers find the next layer. | DRQG 1.0.3 needed three independent review rounds after its fix agent reported green tests; each round reproduced new fail-open inputs (wrong types, trusted self-declared sources, default-clean missing fields, denylists, poisoned aliases). | Run an executing adversarial code review on every candidate before `evaluation:prepare`, and repeat until a round reproduces nothing. Checklist items A5a, B1a, C5, D11, D12 and G2a. For Wave 1 the exit is relaxed to a round with only low-severity defects; see the [Wave 1 QA exit waiver](#wave-1-qa-exit-waiver-2026-10-05). |
| Phrase-list detectors don't generalise, and a held-out set leaks easily. | Each QA round found new instruction-like paraphrases the three plugins' detectors missed (7, 16 and 13 of 40 held-out lines caught). The shared detector then scored 38/40 on the first held-out set (2026-10-01a), but an overlap check found 16 of its 70 lines in the detector's corpus, via examples in the operator's own brief and benign lines taken from plugin tests. On the clean set (2026-10-01b, 0/70 overlap) detector 1.1.0 scored 34/40 (85%) with 0/30 false positives, below the 90% bar. 1.1.1 then scored 39/40 on that set, but fresh lines written after its misses were described scored only 17/28: describing a missed class to the detector author let it fit the wording, not the structure. 1.1.2, built against structural briefs and the author's own blind holdouts, scored 25/31 on a fresh set (1.1.1: 10/31): structure generalises, but regex rules plateau below 90% on open-ended wordings. | One shared detector (`shared/steering-guard/`, checklist D14 and D15), scored against a private held-out set that is checked for overlap and never used as examples (runbook "Creating a held-out set"). |
| A defect found in one plugin is a class to sweep in all of them. | Pre-freeze QA rounds 1–5 on DRQG, T&E and Mobilization kept finding the same shapes in different plugins: later stages trusting intermediates, unscreened JSON keys and metadata subtrees, instructions split across array entries, duplicate CSV headers, holds merged after gating, and errors echoing input. | Send each confirmed defect to every plugin's fix agent as a class sweep, and record it in the checklist (A11 to A23, B5, B6, D16 to D21). |
| Field-by-field reconciliation never converges. | Mobilization QA rounds 13 and 14 and T&E round 11: after each per-field reconciliation fix, the next round edited a different carried field (a roster responsibilities entry, a proposed role title, an appended excluded item, a deleted excluded-entry record) and it reached the output (`6b33a13`, `b379a94`, `777620f`). | Each downstream stage re-runs the upstream derivation on the screened raw inputs and requires deep equality on every engine-owned field, provenance included, with a justified allow-list; the final rendering step runs the same check. Checklist A23 (`dfbce9f`, `ace121a`). This is the reason for the [Wave 1 QA exit waiver](#wave-1-qa-exit-waiver-2026-10-05). |
| Long suites and silent runs stall the operator's session, not the plugin. | "DRQG keeps hanging" (2026-10-06): the DRQG round 17 and T&E round 14 fix agents finished with green suites but their completion notices never reached the orchestrating session, which kept waiting until its host failed; nothing was committed. Suites had grown to 7–10 minutes and ran in parallel, and `evaluation:prepare` ran the shipped suite silently with no timeout. | Full suites run one at a time under a lock, once per agent; agents iterate with `--group`. Orchestrators check agent status directly instead of waiting for notices, and start a fresh session rather than resuming a stalled one. Shipped runners stream results (checklist G7); `evaluation:prepare` streams the suite with a timeout; the Cowork prompt tells the evaluator a suite may take about 15 minutes. Runbook "Running suites and agents" (`70d856a`, `17f9c82`). |

## Wave 2 queue and substitute

Wave 2 follows Wave 1 in the order set by the 2026-10-01 rerank. Scores are kept in the
confidential scenario document and are not repeated here.

| # | Plugin | Slug | Repo version | Evaluation state |
|---|---|---|---|---|
| 06 | Client Status & QBR Assembly | `client-status-qbr` | 1.6.2 | Published at 1.4.0 (Ready). 1.6.1 evaluated **Blocked** and archived. 1.6.2 frozen (`E225B295…A6F3`), not yet evaluated. |
| 07 | SOW Drafting from Scoping Notes | `sow-drafting-scoping-notes` | 1.0.0 | Built, not evaluated. |
| 08 | Credential & Case Study Assembly | `credential-case-study-assembly` | 1.0.0 | Built, not evaluated. Consumes Closeout's sanitised knowledge record. |
| 09 | Engagement Financial Health Brief | `engagement-financial-health-brief` | 1.0.0 | Built, not evaluated. |
| 10 | Conflicts & Independence Pre-Check | `conflicts-independence-precheck` | 1.0.0 | Built, not evaluated. |

**Lead substitute: Change Order & Scope Control** (`change-order-scope-control`, 1.0.0). It left
the top ten in the rerank but stays built. A 1.0.0 candidate was frozen before the rerank
(`C58DF382…7C4D`) and never evaluated. It returns to the queue only if a launch scenario stalls.
Expect the most trigger-phrase collisions on this plugin and a raised launch floor from its
guardrail wording.

Before evaluating any Wave 2 plugin, apply the [hardening checklist](../plugin-hardening-checklist.md)
first, as was done for DRQG. The four 1.0.0 builds predate every lesson above.

## Open risks

| Risk | Effect | Mitigation |
|---|---|---|
| Human reviewer availability | 01 and 02 are blocked on two independent reviewers, and no reviewers have been named. Every later Ready plugin joins the same queue. | Line up reviewers before more plugins reach Ready. The trackers and critical paths are ready to hand over. |
| Evaluator stochasticity | Reruns of the same ZIP can disagree, as T&E 1.0.1 showed. | The canonical hash-matched run is authoritative. If a verdict is disputed, fix and re-version; do not rerun the same version for a better answer. |
| Evaluator evidence gates vary by run | On 2026-10-07, DRQG 1.0.4 was Blocked solely because installed-runtime evidence and human grader labels were missing, while the Mobilization 1.0.1 run the same day did not apply that gate. Any candidate can be blocked this way regardless of quality. | Record such a block as "missing evidence", not a plugin defect, and do not re-version for it. Installed-runtime evidence comes from the two-reviewer critical-path runs (C2). |
| Mobilization value framing | The scenario has no external quantification, so a reviewer may push for figures. | Frame value as cycle time and risk avoided. Do not invent percentages or hours. |
| DRQG over-escalation perception | The broad `is_definitive_conclusion` rule and fail-closed registers raise more release blockers (Scenario B has 6). A judge or reviewer may read this as noise. | The rule is deliberate. If a run marks it down, tune with evidence from the report; do not quietly relax fail-closed behaviour. |
| Thin health margin on Closeout `sanitize-check` | 82 against an 80 floor; a rerun could fall below. | Backlog item 4 in [01](#open-backlog-non-blocking-candidates-for-an-optional-103). |
| Dirty-worktree receipts | Receipts for early freezes record HEAD `1eaaee4`, not the source. | The ZIP SHA-256 is still authoritative. Commit before future freezes. |
| Trackers are sensitivity-labelled | Sign-off state cannot be checked by script; `openpyxl` and LibreOffice cannot open the workbooks. | Check them in Excel desktop or through Excel COM automation, and record only the gate status here. |
| Test-suite runtime growth | Measured 2026-10-05, run serially on one machine with endpoint scanning active: Mobilization 49 s (2026-10-01 baseline) to 65–71 s at `b9295dd` (390 checks); T&E 81 s to 100 s (957 checks); DRQG 57 s to 124–136 s (1,159 checks), and 147–154 s with the A23 sweep (`9c45c0c`, 1,267 checks). The instruction detector scales linearly. Most of the growth is repeated file reads in the test harnesses (20–39% of profiled time in file opens, made slower by endpoint scanning) and the whole-chain re-derivation required by A22 and A23. Mobilization's one wall-clock check failed at 20 s under ordinary load and was raised to 60 s (`2076c12`). Re-measured 2026-10-05 evening after QA rounds 12 to 19: Mobilization 210–250 s (483 checks), T&E 440–500 s (1,186 checks), DRQG 300–325 s (1,509 checks). | Accepted for Wave 1: every suite finishes well within the one-hour ceiling, which `evaluation:prepare` also has to fit. Harness-side read caching (never in the engines; mutated fixtures and A23 refusal tests always run the production engines) is backlog after the Wave 1 freezes. The load-sensitive wall-clock check is replaced by a per-call bound (`c461e3d`). At the 2026-10-07 freezes, run serially from the ZIP: Mobilization 385 s (525 checks), DRQG 429–473 s (1,716), T&E 13–15 min (1,283); `evaluation:prepare` took 7, 9 and 15 minutes. |

## Frozen artefact register

Every Wave 1 candidate frozen so far. SHA-256s are from the `evaluation-run.json` receipts. For
versions archived before 14:00 PT, the ZIP under `Evaluation\<version>\` was re-hashed on 2026-10-01
and matched; T&E 1.0.3 relies on the hash check `evaluation:archive` performs before it archives.

| Plugin | Version | Cowork task name | Full SHA-256 | Receipt commit | Verdict |
|---|---|---|---|---|---|
| Closeout | 1.0.0 | `evaluate-engagement-closeout-knowledge-harvest-v1.0.0-2026-10-01` | `527B98067E1968C4FB8D201967EC11258430B91CABB066858F302FEEC54937E7` | `1eaaee4` (dirty) | Blocked |
| Closeout | 1.0.1 | `evaluate-engagement-closeout-knowledge-harvest-v1.0.1-2026-10-01` | `402FCF06F13B1AC97E6DFA1619FE1D21AB28ABABF8CC642B628C368DE8C61992` | `1eaaee4` (dirty) | No-ship |
| Closeout | 1.0.2 | `evaluate-engagement-closeout-knowledge-harvest-v1.0.2-2026-10-01` | `5F5F8123F23BF7705216346BAC1B7AA3438168920B5286579D9746FD971C1782` | `1eaaee4` (dirty) | Ready |
| Staffing | 1.1.2 | `evaluate-engagement-staffing-bench-match-v1.1.2-2026-09-30` | `1C00A047043FABA723A9DE524861ADEE4050D0C97E6B35EE8C3AD1ED7A8588E6` | `1eaaee4` (dirty) | No-ship |
| Staffing | 1.1.3 | `evaluate-engagement-staffing-bench-match-v1.1.3-2026-09-30` | `FEE1057799D8EF69BD7BF805C3662D8687CB93E9A4A2337B65511F201261FD09` | `1eaaee4` (dirty) | No-ship |
| Staffing | 1.1.4 | `evaluate-engagement-staffing-bench-match-v1.1.4-2026-09-30` | `4BDE82D9959499AEE974D3963879CED6B680C0127AAAE3DAD0DADBB9BC0A9C06` | `1eaaee4` (dirty) | Ready |
| Mobilization | 1.0.0 | `evaluate-engagement-mobilization-onboarding-pack-v1.0.0-2026-10-01` | `A84F5F41F21C6BAE8C1CD6AD2E6D7816C61D240435B0C0D5CCC7DC65CF079F5C` | `1079d97` (dirty) | Blocked |
| T&E | 1.0.1 | `evaluate-time-expense-narrative-compliance-v1.0.1-2026-10-01` | `5A77AFF0C33210C1C57314639E7FE8815C9645E26D6E57DF25DBB91A5AD38A3E` | `1eaaee4` (dirty) | Blocked |
| T&E | 1.0.2 | `evaluate-time-expense-narrative-compliance-v1.0.2-2026-10-01` | `1D2B465A1DE214A24185BE24850BB00EBA3C09FA8CC7C0B75C5CA1D028E33A74` | `1eaaee4` (dirty) | Not evaluated (superseded) |
| T&E | 1.0.3 | `evaluate-time-expense-narrative-compliance-v1.0.3-2026-10-01` | `53A5C7EC29C4F4803AAD922BA04DBACA41C30576B6464B8460E0C55E0183E652` | `88b5b41` (dirty) | Blocked |
| DRQG | 1.0.1 | `evaluate-deliverable-review-quality-gate-v1.0.1-2026-10-01` | `7F487D5D85324022655EC3A444E70B74CEEF19B3C9C2CE3003EFAF122D8849BC` | `94a6192` (dirty) | No-ship |
| DRQG | 1.0.2 | `evaluate-deliverable-review-quality-gate-v1.0.2-2026-10-01` | `29B431EC62455E68E53AAD236698BFADA2518DA8BDA0F65EC2624D9852E5B869` | `2ba4145` (dirty; rewritten to `7626d67`, see note) | Blocked |
| DRQG | 1.0.3 | `evaluate-deliverable-review-quality-gate-v1.0.3-2026-10-01` | `99699BDDDA3407FC6720AE57FD47116D0F2E9A9A94D60ABD5217B130FED0F9D2` | `581a144` (dirty: docs only; rewritten to `7d09dd1`, see note) | Blocked |
| Mobilization | 1.0.1 | `evaluate-engagement-mobilization-onboarding-pack-v1.0.1-2026-10-07` | `40D3968EA98ADF4D68B9D1141292A4A2704E75F5521EE0C88B2938EDF33A9EC1` | `f9518fd` (clean) | No-ship |
| DRQG | 1.0.4 | `evaluate-deliverable-review-quality-gate-v1.0.4-2026-10-07` | `4AE3153080717D0BD55353064020EE56045ED81B50E31954A059B621D620316B` | `f9518fd` (clean) | Blocked (missing evidence) |
| T&E | 1.0.4 | `evaluate-time-expense-narrative-compliance-v1.0.4-2026-10-07` | `1E1380E38349678E030CAC4486CC804937B51DEFF51739ABBE2F0729181F10B4` | `f9518fd` (clean) | In Cowork evaluation |

The task name is the one `evaluation:prepare` suggested. Some Cowork tasks were created under
different display names; the watcher matches by SHA-256, so this does not affect the evidence.

The receipt commit column shows what each receipt records. Commit 2ba4145 was rewritten to 7626d67
before first push (history scrub of an internal URL; plugin files identical). A second pre-push
scrub removed an internal site name from the SharePoint-sync script, its test and its doc; plugin
files were untouched, and 581a144 became 7d09dd1. Frozen receipts and archived reports cite the
pre-rewrite SHA.
