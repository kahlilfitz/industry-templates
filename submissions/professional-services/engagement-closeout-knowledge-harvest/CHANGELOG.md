# Changelog

Earlier versions (1.0.0 to 1.0.2) are recorded in the git history of this folder.

## 1.0.3 - 2026-10-12

MOS3 packaging release plus the full plugin-hardening checklist (sections A to H). The output
contract stays `ps.engagement-closeout-knowledge-harvest.v1` and every change to it is additive: no
field was removed, renamed or retyped, so the governed `knowledge_record` read by Credential & Case
Study Assembly and by the Engagement Mobilization & Onboarding Pack Scenario 01 adapter
(`knowledge_match.py` reads `engagement`, `provenance`, `released_assets` and
`knowledge_record.reusable_assets` and `lessons`) still loads; that adapter passes against the new
Scenario A golden. Every golden difference is listed under *Golden differences* below.

- **MOS3 package.** The plugin is now a Microsoft 365 app package (manifest 1.28) instead of the
  Claude plugin layout. Added `manifest.json` (new stable GUID `id`, `accentColor` `#0B6A7A`,
  `agentSkills` listing the five skill folders), `color.png` and `outline.png`; removed
  `.claude-plugin/`. `metadata.json` sets `"packageFormat": "mos3"`. The ZIP now holds only
  `manifest.json`, the two icons and `skills/`.
- **Test data moved out of the plugin.** `demo-data/` and `tests/` moved to
  `test-data/professional-services/engagement-closeout-knowledge-harvest/1.0.3/` with a README.
  `tests/test_engines.py` follows the runner contract: `--plugin-root <dir>` or `PLUGIN_ROOT`
  (default: this submission folder), `skills/...` resolved against the plugin root and
  `demo-data/...` against the version folder, both roots printed at start, a clear failure when the
  plugin root has no `skills/`, an ASCII-safe `PASS <name>`/`FAIL <name>` line streamed and flushed
  per test, `--list-groups` and a repeatable `--group`, a final `N/M checks passed` line and exit 1
  on any failure. No 1.0.2 test was removed or weakened; each one is kept in its group, and the golden
  test reruns both scenarios and compares every `expected/` file byte for byte, which the 1.0.2 runner
  never did. See *Hardening* for the suite as frozen (97 tests in 15 groups).
- **Root dev copies removed.** The root `contracts/` and `references/` folders duplicated the copies
  every skill already carries and nothing outside the old test read them. The shared-copy test now
  checks that all five skills hold byte-identical copies of the contract and the three references.
- **Skill descriptions rewritten** to the Partner Team Guide shape: two sentences on what the skill
  does and when, six quoted trigger phrases (none shared between skills) and one `Do NOT use for ...
  (use <sibling>)` line that keeps every sibling exclusion and the safety exclusions (no publishing,
  sending, clearing a HOLD or releasing on a claimed approval). All are under 800 characters.
- **SKILL.md frontmatter.** Added `compatibility` (runtime and data each skill needs) and
  `metadata.icon` (Fluent icon ID); `metadata.version` is 1.0.3. Each skill body now shows the exact
  output structure (JSON shape for the engine outputs and assembled payload, table or Markdown
  skeleton for what the user sees).
- **Runtime paths.** No skill file referenced anything outside its own folder; engines read and
  write only `--input` and `--out`. No path changes were needed.
- **Engine version constants** bumped to `asset_identify/1.0.3`, `lesson_cluster/1.0.3` and
  `sanitize_check/1.0.3`. Downstream fixtures that record `/1.0.2` (for
  example Mobilization's `upstream/closeout-governed.json`) are historical inputs, and no downstream
  skill validates this version string.
- **LF output.** The three engines now write `--out` with `newline="\n"`. They previously wrote CRLF
  on Windows, so their output did not match the LF goldens byte for byte.
- Added `listing-metadata.md` (store listing draft; not packaged).

### Hardening (plugin-hardening-checklist A to H)

1.0.2 passed evaluation before checklist section D existed. 1.0.3 closes every applicable item.

- **One shared engine core.** `closeout_core.py` holds the loader, the input validator, the
  screen, the three stages, the knowledge-record skeleton and the replay. It ships byte-identical in
  `scripts/` of asset-identify, lesson-cluster, sanitize-check and knowledge-record.
  `asset_identify.py`, `lesson_cluster.py` and `sanitize_check.py` are now thin CLIs that call it.
- **Embedded-instruction screen (D1-D24).**
  - **Detector.** `shared/steering-guard/steering_guard.py` (1.1.2) is vendored byte for byte
    beside each core. Closeout vocabulary reaches it only through the documented hooks
    `extra_verdict_words`, `extra_rule_nouns` and `contact_is_steering`; there are no private
    phrase lists.
  - **What is screened, and when.** Every supplied free-text value is screened before any rule
    reads it (D10): engagement, artifact, asset, decision, retrospective and terms fields, list items
    and upstream escalations.
    - Each value is screened line by line and in adjacent line pairs.
    - It is also joined with the other fields of its record (D22) and with any field of the
      adjacent record in the same list (D18), and screened as runs of adjacent list items.
    - IDs, marker tokens and sources are screened with `-_.:` read as spaces, and each
      `:`-separated segment is screened on its own. A hit refuses the input (D13).
  - **What happens to flagged text.** It is replaced with a fixed placeholder and recorded in a
    new `screening_holds` array: path, location, family, reason, source and citation, never the
    text (D8).
    - An asset with withheld text is held as `HOLD_EMBEDDED_INSTRUCTION`.
    - Withheld evidence clusters as `unclassified` and decides nothing (D19).
  - **Client name.** A withheld client name holds every asset as `HOLD_IDENTITY_UNSCREENABLE`
    (#8.3).
  - **Rendered skeleton.** Before `sanitize_check.py` returns, it screens the rendered skeleton.
    A rendered-only hit withholds the contributing values (location `rendered`), and the chain is
    derived again (#8.2, B6).
- **Strict validation (A).** Each engine refuses bad input with one clean stderr line, exit 2,
  writes nothing and never echoes the offending value. It refuses:
  - an unknown key or a wrong type;
  - NaN, a boolean or an out-of-range number;
  - a duplicate or malformed ID;
  - a non-UTC or mismatched `--generated-at`;
  - over-deep JSON;
  - an engine-owned section supplied as input;
  - an unbound withheld placeholder.

  Unknown markers and aggregation tokens hold their asset as `HOLD_UNRECOGNISED_MARKER` (#7.4).
  Empty `confidentiality_terms` hold every asset as `HOLD_TERMS_UNAVAILABLE` (#7.5).
- **Whole-document integrity (C, B5).** Every later stage re-derives each engine-owned section
  from the screened input it carries and refuses a forged or edited intermediate. Precedence is
  order-independent (B2), de-duplication never lowers a state, and a group aggregation hold also
  moves each member asset's own finding (B3, #5.2).
- **Draft check (E1-E11).**
  - `knowledge-record/scripts/record_check.py` writes the deterministic skeleton, with the
    `DRAFT - HUMAN REVIEW REQUIRED` label and fixed lines.
  - It refuses a filled draft that changes a fixed line, or whose context or lesson slot carries
    any of:
    - an instruction, a withheld marker, the client name or descriptor, or a sector-region pair;
    - a date, the headcount, a third-party product or a named person;
    - a held ID or title, copied stage guidance, or six or more copied source words.
  - Stage guidance (`drafting_guidance`) is never rendered as content (E10).
- **References and descriptions.**
  - Every cited reference section now names the state it produces (E7).
  - `artifact-assemble/references/closeout-ingest-rules.md` documents how each raw file maps to
    `engagement.json` (G4b).
  - Every SKILL.md carries the same untrusted-data guardrail block (D9, E9).
  - Each description's single `Do NOT use for` line now also defers to the adjacent plugin
    (Engagement Mobilization Pack or Deliverable Quality Gate) and keeps the never-clear or
    never-publish exclusion (F1); all are 800 characters or fewer.
- **Additive contract fields.**
  - `screening_holds` in each output.
  - `provenance.screening`, `provenance.policies` and `provenance.input_escalations`.
  - `knowledge_record.draft_label`.
  - New `clearance_state` members and finding target types (`screening`, `register`,
    `engagement`).
  - The contract schema now states the strict input rules: required members, ID, token and
    `skill:`/`connector:` source patterns, and `additionalProperties: false`. On the output side,
    sections only gain members and `enum`/`const` values.
- **Tests.** `test-data/.../1.0.3/tests/test_engines.py` has 97 tests in 15 groups. It ships with:
  - `steering-corpus.json`, a byte-identical copy of `shared/steering-guard/corpus.json`;
  - `closeout-steering-sets.json`, the closeout sets: 25 attack lines, 14 paraphrases, 26 benign
    closeout and lessons lines, 7 attack pairs, 5 benign pairs, and 19 recorded detector gaps,
    each tested as mitigated;
  - `check_shared_copies.py`.

  Each of these is run through the real call sites. The G4b test re-derives each scenario's
  `engagement.json` from its raw pack. Representative new fixtures fail on the pre-hardening engines
  (G1): an instruction is echoed, a wrong type raises a traceback, and forged intermediates are
  accepted.
- **Known detector limit.** The detector hooks cannot add authority-claim or suppression patterns,
  so the 19 recorded `detector_gaps` lines pass the screen. The design still keeps them out of the
  output:
  - supplied free text is never rendered into the knowledge record (only engine-built lines and
    reviewer-written slots are);
  - `record_check.py` refuses any slot that copies six or more source words.

  `shared/` was not edited.

### Golden differences

- **Both scenarios, all three JSON goldens.** New additive keys:
  - `screening_holds: []`;
  - `provenance.input_escalations: []`;
  - `provenance.policies` (the reference sections each stage applied);
  - `provenance.screening` (detector version and hook profile).

  `governed.json` also gains `knowledge_record.draft_label`.
- **Raw packs made derivable (G4b).** The raw packs did not support the structured inputs:
  - Retrospective transcript entries now carry their evidence IDs (`[RET-001]`, and
    `[RET-202 | named: Maya Patel]`).
  - Terms clauses carry their term IDs (`TERM-01`, `TERM-11`, `TERM-12`).
  - Each scenario gains `raw/engagement-profile.md` and `raw/asset-nominations.csv`.
  - Scenario B's run-together lines 16-19 are split, so RET-203 cites lines 16-17 and AST-105
    cites lines 18-19.
- **Inputs re-derived from the raw packs.**
  - `engagement.citation` is now `raw/engagement-profile.md`.
  - Scenario A TERM-01 `summary` is the exact clause text.
  - Scenario B decision-log and register citations are corrected to the real CSV rows (row 1 is
    the header): DEC-201, DEC-207 and AST-103 move from decision rows 4-5 to rows 2-3, and AST-104
    moves from register row 6 to row 7.
- **Scenario A, DEC-014.** DEC-014 scores equally for two categories. A tie is now `unclassified`
  (lesson-taxonomy #1.5) and a review candidate, instead of being resolved by category order. RET-001
  therefore leaves LC-001 and forms LC-003 (delivery-governance, score 60). As a result, `lesson_cluster`
  stdout reads 3 clusters and 1 review candidate.
- **Scenario A, AST-003.** AST-003 carries the `client_specific_configuration` marker, which no 1.0.2
  rule read. The new #1.3 rule holds it as `HOLD_REDACTION_REQUIRED`, which ranks above
  `HOLD_NOT_SHORTLISTED` in the #7.3 precedence; both reasons are kept.
- **Scenario B, AST-101 and AST-102.** Their own findings move from `RELEASE_CANDIDATE_SANITISED` to
  `HOLD_AGGREGATION_RISK` (#5.1, #5.2), matching their group hold, so no finding for a held asset
  reads as a release candidate.
- **New example files.** `expected/knowledge-record-skeleton.md` and
  `expected/knowledge-record-draft-example.md` (a reviewer-filled draft that `record_check.py`
  accepts) are new in each scenario.
