# engagement-staffing-bench-match - tests and demo data

Demo data and the regression suite for the **engagement-staffing-bench-match** plugin. They live
in the submission folder (`submissions/professional-services/engagement-staffing-bench-match/`)
beside `skills/`. None of this ships in the MOS3 package; the package holds only `manifest.json`,
the two icons and `skills/`.

```text
engagement-staffing-bench-match/
├── skills/ ...             the plugin (packaged)
├── demo-data/
│   ├── scenario-a-happy/   roles.json, bench.json, constraints.json, raw/, expected/
│   └── scenario-b-drama/   roles.json, bench.json, constraints.json, raw/, expected/
└── tests/
    ├── README.md               this file
    ├── test_engines.py         the runner
    └── sample-test-prompts.csv human spot-check prompts with expected results
```

## Running the suite

Run from `submissions\professional-services\engagement-staffing-bench-match\`. The runner prints the plugin root and data root it resolved, then an
ASCII-safe `PASS <group>: <test>` or `FAIL <group>: <test>` line (flushed) as each test finishes,
with the traceback indented under any `FAIL`. The last line is `N/M checks passed`; the exit code is
1 if any check failed and 2 for a usage error (unknown group, or no `skills\` under the plugin root).

Against the source submission (the default plugin root, the folder holding `tests\`, when neither
`--plugin-root` nor `PLUGIN_ROOT` is set):

```powershell
python tests\test_engines.py
```

Against a built package, extract `public\bundles\engagement-staffing-bench-match.zip` to a
folder and pass it as the plugin root (or set the `PLUGIN_ROOT` environment variable):

```powershell
Expand-Archive public\bundles\engagement-staffing-bench-match.zip $env:TEMP\esbm-zip
python tests\test_engines.py --plugin-root $env:TEMP\esbm-zip
```

`skills/...` paths resolve against the plugin root and `demo-data/...` paths against the submission
folder (the parent of `tests\`), so the working directory does not matter. The runner stops with a clear
error if the plugin root has no `skills\` folder.

To run part of the suite, list the groups and pass `--group` once per group:

```powershell
python tests\test_engines.py --list-groups
python tests\test_engines.py --group golden-scenarios --group shared-copies
```

The groups, in run order, are `constraint-check`, `fit-score`, `slate-validate`, `shared-copies`,
`package-layout` and `golden-scenarios`.

## What the suite covers

- **Engine regression** (`constraint-check`, `fit-score` and `slate-validate` groups): fail-closed
  conflict and affiliate matching, availability time-weighting, missing-data reviews, score floor,
  injection redaction (including the evaluator's paraphrase, homoglyph, full-width and zero-width
  variants, and benign prose that must not be redacted) and the secondary safety check in
  `slate_validate`.
- **Shared copies** (`shared-copies`): the contract and both references in every skill are
  byte-identical to the canonical copies in `skills/fit-score/`, and `scripts/safety_text.py` in
  `constraint-check` and `slate-draft` is byte-identical to the `fit-score` copy.
- **Package layout** (`package-layout`): every skill has its `SKILL.md`, carries no demo data
  or tests and references nothing outside its own folder.
- **Goldens** (`golden-scenarios`): runs `fit_score` → `slate_rank` → `constraint_check` →
  `slate_validate` from the plugin root on both scenarios, in a fresh working directory, and requires
  each stage to match `expected/*.json` byte for byte (line endings aside: on Windows the engines
  write CRLF, while the goldens are stored with LF).

## Scenarios

- **`scenario-a-happy`**: two open roles and a clean bench and conflicts extract. Ava Morgan is
  recommended first for `PSS-001` and Leo Brooks for `PSS-002`, with no top-candidate refusals or
  gaps; lower-ranked alternatives are still held by availability.
- **`scenario-b-drama`**: the obvious answer is wrong. Mina Patel ranks first for `PSS-101` but is
  refused for an unresolved material financial interest (`#3.1`, `#7.1`), so Owen Ramos is
  recommended; Nico Stone shows 0% allocation but approved leave plus a soft-booked pursuit leave
  77.6% effective capacity against 80% requested (`#6.2`); `PSS-102` gets a gap statement because no
  eligible candidate meets the 70.0 floor. The `C-201` bench citation carries a prompt-injection
  fixture that every engine must redact.

Each scenario folder has its own `README.md`. Start from `raw/` to exercise the Connect path or
from the structured JSON to exercise the engines. `sample-test-prompts.csv` paths such as
`demo-data/scenario-a-happy` are relative to the submission folder.

## Ingest rules

Hardening item G4b: every value in a scenario's `roles.json`, `bench.json` and `constraints.json`
appears in, or follows by one of these rules from, that scenario's `raw\` pack.
`tests\derive_inputs.py` (standard library only) re-derives all three files from `raw\` and
`tests\test_demo_derivation.py` (`DemoInputDerivationTests`) diffs them against the fixtures by
JSON path; run it with `python -m unittest discover -s tests -p test_demo_derivation.py`. If you
change a raw file or a fixture, change the other (or a rule here) in the same commit.

`roles.json` (role-intake) from `sow-role-extract.md` and `staffing-request-email.txt`:

- Engagement: `engagement_id` is the header's internal engagement code (if absent, the SOW ID plus
  an escalation); `client_name`, `affiliates` (`;`-separated), `practice`, `stage` and every role's
  `industry_context` come from the header lines; citation `SOW extract <SOW ID>, header and
  staffing request email`.
- Roles, one per table row: seniority lowercased (must be canonical); `N weeks`, `N%` and
  `USD a-b/hr` become integers; `<City> or remote` sets `remote_ok` true and `<City> only` false;
  skill and certification cells split on `;` (`None` is empty); `required_languages` is the header's
  working language plus any `<Language>-speaking` in the role title; citation `SOW <SOW ID> section
  <section> role <row number>`.
- Confidence: the request paragraph or numbered item naming the role title (title removed) is
  searched, case-insensitively, for the allocation, start date, duration, city and every required
  and preferred skill and certification: all found 0.96, some 0.95, none or role not named 0.94.
  `engagement.confidence` is 0.96 when the request names the client, else 0.94.
- Escalations: "`<Name>` is the [obvious|preferred|right|best] pick|choice" in the request becomes
  `<role_id>: staffing request names <Name> as a preferred candidate; recorded as context only and
  excluded from scoring and eligibility (role-intake step 4)`, for the role named in that paragraph.

`bench.json` (bench-query) from `bench-roster.csv`: one candidate per row, `;` lists (empty cell is
`[]`), integer rate and percentages, and the row's `citation` column verbatim (the `C-201`
injection fixture included; the engines redact it). An availability cell `<ID> <start>..<end> <N>%`
becomes `{start, end, allocation_pct}` cited `leave calendar request <ID>` or `pursuit soft-book
<ID>`. `confidence` applies the bench-query step 5 ladder to the evidence columns, which are not
carried: `profile_enrichment` `none` 0.95; else a non-blank `secondary_source` 0.97; else
`availability_verified` `yes` 0.98; else 0.96. `roles` and `escalations` are empty.

`constraints.json` (bench-query step 4) from `conflicts-register-extract.csv`: one record per row
with `candidate_id`, `type`, `client_name` and `status`; `material`, `role_type`, `process`,
`end_date` and `resolved_date` only when non-blank (`material` `true`/`false` as a boolean); the
row's `citation` verbatim; `confidence` 0.97 for every row and the extract (one evidence tier per
extract). The top-level citation is `conflicts extract <CF ID>` from the register ID in the rows.
It has no `escalations` or `provenance`.

Shared constants: `contract_version` `ps.engagement-staffing-bench-match.v1`; sources
`skill:role-intake`, `connector:resource-management-system` and `connector:conflicts-register`;
`bench.json` and `constraints.json` copy `engagement{}` from `roles.json`, and `constraints.json`
copies `roles[]`; `provenance` (roles and bench only) is `{"generated_at": "2026-09-23T21:20:34Z",
"demo_scenario": "<scenario folder>"}`, the demo-pack build stamp rather than a source fact.
