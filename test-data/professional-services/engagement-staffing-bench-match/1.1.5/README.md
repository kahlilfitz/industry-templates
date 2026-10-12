# Test data: engagement-staffing-bench-match 1.1.5

Demo data and the regression suite for the **engagement-staffing-bench-match** plugin, version
**1.1.5** (`submissions/professional-services/engagement-staffing-bench-match/`). None of this
ships in the MOS3 package; the package holds only `manifest.json`, the two icons and `skills/`.

```text
1.1.5/
├── README.md
├── demo-data/
│   ├── scenario-a-happy/   roles.json, bench.json, constraints.json, raw/, expected/
│   └── scenario-b-drama/   roles.json, bench.json, constraints.json, raw/, expected/
└── tests/
    ├── test_engines.py         the runner
    └── sample-test-prompts.csv human spot-check prompts with expected results
```

## Running the suite

Run from this folder. The runner prints the plugin root and data root it resolved, then the
unittest result; it exits non-zero on any failure.

Against the source submission (the default when neither `--plugin-root` nor `PLUGIN_ROOT` is set):

```powershell
python tests\test_engines.py
```

Against a built package, extract `public\bundles\engagement-staffing-bench-match.zip` to a
folder and pass it as the plugin root (or set the `PLUGIN_ROOT` environment variable):

```powershell
Expand-Archive public\bundles\engagement-staffing-bench-match.zip $env:TEMP\esbm-zip
python tests\test_engines.py --plugin-root $env:TEMP\esbm-zip
```

`skills/...` paths resolve against the plugin root and `demo-data/...` paths against this folder
(the parent of `tests\`), so the working directory does not matter. The runner stops with a clear
error if the plugin root has no `skills\` folder. Other arguments go to `unittest` (for example
`-v` or `ConstraintCheckTests`).

## What the suite covers

- **Engine regression** (`ConstraintCheckTests`, `FitScoreTests`, `SlateValidateTests`): fail-closed
  conflict and affiliate matching, availability time-weighting, missing-data reviews, score floor,
  injection redaction (including the evaluator's paraphrase, homoglyph, full-width and zero-width
  variants, and benign prose that must not be redacted) and the secondary safety check in
  `slate_validate`.
- **Shared copies** (`SharedCopyTests`): the contract and both references in every skill are
  byte-identical to the canonical copies in `skills/fit-score/`, and `scripts/safety_text.py` in
  `constraint-check` and `slate-draft` is byte-identical to the `fit-score` copy.
- **Package layout** (`PackageLayoutTests`): every skill has its `SKILL.md`, carries no demo data
  or tests and references nothing outside its own folder.
- **Goldens** (`GoldenScenarioTests`): runs `fit_score` → `slate_rank` → `constraint_check` →
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
`demo-data/scenario-a-happy` are relative to this folder.

## Freezing

This folder is frozen once version 1.1.5 is evaluated: `npm run evaluation:prepare` writes
`FROZEN.sha256` here and `npm run check:test-data` then fails on any change. A new plugin version
copies this folder forward to a new version folder and changes the copy.
