# Tests and demo data: engagement-mobilization-onboarding-pack

Demo data and the regression suite for the **engagement-mobilization-onboarding-pack** plugin. They
live in the submission folder (`submissions/professional-services/engagement-mobilization-onboarding-pack/`)
beside `skills/`, but none of this ships in the MOS3 package; the package holds only `manifest.json`,
the two icons and `skills/`.

```text
engagement-mobilization-onboarding-pack/
├── demo-data/
│   ├── scenario-a-happy/   raw/, upstream/, expected/
│   └── scenario-b-drama/   raw/, upstream/, expected/
└── tests/
    ├── README.md                this file
    ├── run_tests.py             the runner (streams PASS/FAIL per check, grouped)
    ├── steering-corpus.json     the steering-guard corpus the vendored detector is scored against
    └── sample-test-prompts.csv  human spot-check prompts with expected routing and results
```

## Running the suite

Run from the submission folder. The runner prints the plugin root and data root it resolved first. It
then prints `PASS <label>` or `FAIL <label> (detail)` as each check runs, under a
`== group <name>` header, repeats any failures under `== failures`, and ends with
`N/M checks passed` (exit 1 on any failure). A full run takes about ten minutes.

Against the source submission (the default when neither `--plugin-root` nor `PLUGIN_ROOT` is set):

```powershell
python tests\run_tests.py
```

Against a built package, extract `public\bundles\engagement-mobilization-onboarding-pack.zip` to a
folder and pass it as the plugin root (or set the `PLUGIN_ROOT` environment variable):

```powershell
Expand-Archive public\bundles\engagement-mobilization-onboarding-pack.zip $env:TEMP\emop-zip
python tests\run_tests.py --plugin-root $env:TEMP\emop-zip
```

`skills/...` paths resolve against the plugin root and `demo-data/...` and `tests/...` paths
against the submission folder (the parent of `tests\`), so the working directory does not matter.
The runner stops with exit 2 and a clear error if the plugin root has no `skills\` folder.

- `--list-groups` prints the check group names, one per line.
- `--group NAME` (repeatable) runs only those groups, in suite order, after the shared scenario
  chain setup; for example `python tests\run_tests.py --group core` for the goldens or
  `--group mos3_checks` for the package-layout checks.
- An unknown group or argument exits 2.

## What the suite covers

- **Goldens** (`core`): runs `scope_digest` → `knowledge_match` → `wall_check` →
  `access_checklist` on both scenarios with `--generated-at 2026-10-01T00:00:00Z` and requires the
  five outputs to match `expected/` byte for byte.
- **Fail-closed and negative fixtures** (`core`, `extra_checks`, `core_tail` and the `qa101*`,
  `qa102*`, `r15_sweep_tests` groups): a missing or malformed ethical-wall register is refused, an
  unknown wall status holds, a missing SOW fails, the Scenario 01 Closeout and Scenario 02 staffing
  adapters refuse a wrong contract version, an intermediate edited in any field is refused by the
  next stage, and the render checks (`verify_render.py`) refuse a supplied scope or pack that the
  engines would not re-derive.
- **Instruction tripwire** (`extra_checks`, `steering_checks` and the QA groups): the plugin's
  benign set (`BENIGN`, must not trip) and attack set (`ATTACKS`, must trip), and the vendored
  `steering_guard.py` detector through this plugin's call sites against `steering-corpus.json`.
- **Routing and SKILL.md** (`v101_checks`): five quoted triggers per description, each owned by one
  skill, identical Guardrails, and failure handling that stops and never hand-builds an output.
- **Package layout** (`mos3_checks`, 1.0.3): every shared contract, reference, helper and engine
  copy is byte-identical to its source (`skills/engagement-retrieve/` is canonical for the contract
  and references); the plugin root carries no `.claude-plugin/`, `config/`, `contracts/` or
  `references/` (and an extracted package no `tests/` or `demo-data/`); no skill file reaches outside its folder; each stage run
  from a lone copy of its skill folder, from an unrelated working directory, reproduces the
  goldens; and every `metadata.version`, the engine `VERSION` stamp and `manifest.json` agree with
  the submission's `metadata.json` version (`PLUGIN_VERSION` in `run_tests.py`).

## Scenarios

- **`scenario-a-happy`** (Orchard Ridge Clinics, `MOB-ORC-1042`): Taylor Reed joins as delivery
  analyst on a confirmed roster with a clear wall. One released Closeout asset (`AST-A-001`, pending practice review)
  is matched, the Closeout lesson `LC-A-001` is excluded because it has no written text, four
  least-privilege access requests are drafted, and the pack is `draft_internal_only`.
- **`scenario-b-drama`** (Nimbus Retail Bank, `MOB-NRB-3100`): Riley Chen is restricted by the
  ethical-wall register, so no prior knowledge is released (`denied_by_wall`), two workspaces are
  denied, one is held pending wall review and one is not requested because it exceeds the role.
  Jules Park is only proposed by Scenario 02, Dana Cho is excluded from the roster as ineligible,
  a source field carrying an embedded instruction is held, and the pack is `on_hold_internal_only`.

Each scenario has `raw/` (the SOW, engagement-letter and pursuit-record extracts, confirmed roster,
wall register and workspace inventory), `upstream/` (the Scenario 01 Closeout governed record and
the Scenario 02 validated staffing output) and `expected/` (the five goldens).
`upstream/closeout-governed.json` keeps Closeout's own engine stamps. `sample-test-prompts.csv`
lists chat prompts against these scenarios with the expected routing and result.

