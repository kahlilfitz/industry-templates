# Plugin details and deployment template

> **Where the filled-in document lives.** Copy this template, fill it in, and save it in the
> SharePoint library at `<Industry>/<plugin-slug>/PLUGIN-DETAILS-AND-DEPLOYMENT.md`, next to the
> plugin's `Evaluation/` folder and human-test tracker. The filled-in document accompanies the
> distributable ZIP and records the human-gate status and the people responsible for it, so it stays
> in SharePoint with the evidence and is never committed to this repository. See
> [What is public and what stays in SharePoint](../release-process.md#what-is-public-and-what-stays-in-sharepoint).
> Delete this blockquote, the required-fields table and every `<!-- guidance -->` comment when you
> fill it in.

Required fields, all of which must be filled before the document is shared:

| Field | Where |
|---|---|
| Evaluated version, evaluated ZIP path, size and file count | Header, section 1 |
| Evaluated ZIP SHA-256 | Section 1 table, sections 7 and 8 |
| Cowork run label | Section 8 |
| Verdict summary table | Section 8 |
| Skill list | Sections 1 and 2 |
| Engines | Sections 1 and 3 |
| Connectors, or "0 - none" | Section 1 |
| Data handling | Sections 4 and 5 |
| Guardrails | Section 4 |
| Deployment and install steps | Section 8 |
| Adaptation guidance | Section 6 |
| Known limitations and backlog | Section 8 |
| Human-gate status | Read-first note and section 8 |
| Change history | Section 7 and the document change history |

Take every number from the archived reports for that version (`plugin-health.html`,
`behavioral-test-report.html` and `recommendations.html`; `full-report.html` before 2026-10-14). Do
not round, re-score or summarise differently from the reports.

---

# <Display name> — Plugin Details & Deployment Notes

Evaluated package: `Evaluation/<version>/<plugin-slug>.zip` · Version <version> · Claude plugin
format (Cowork)

> **Read this first if you are deciding whether to publish.** The Cowork automated verdict for
> <version> is **<Ready | Blocked | No-ship>**, but this is not a publication decision. The
> Industry Templates testing strategy requires **two independent human reviewers** to run every
> prompt in the human-test tracker (the critical-path prompts are the mandatory minimum it must
> contain) and the accountable owner to record a `Publish` decision before the evaluated ZIP can be
> promoted to the plugin-folder-level distributable.

<!-- guidance: If the verdict is Blocked or No-ship, replace the paragraph above with one sentence
stating that this version must not be published and naming the next version being prepared. -->

---

## 1. What's in the package

<!-- guidance: Paste the folder tree of the evaluated ZIP (not the source folder). Annotate each
top-level item and each skill with a short arrow comment. Note which files are vendored into every
skill. The bundler always leaves out the top-level metadata.json, README.md and PACKAGE-NOTES.md,
and leaves out tests/ unless metadata.json sets "bundleTests": true. Those are source-only, so they
never appear in this tree. -->

```text
<plugin-slug>/
├── .claude-plugin/plugin.json      ← identity, description, keywords
├── CHANGELOG.md
├── contracts/
│   └── <contract-file>.json        ← shared contract
├── references/
│   └── <rule-file>.md              ← deterministic rules
├── skills/
│   ├── <skill-1>/                  ← step 1 of <n>
│   └── <skill-n>/                  ← step <n> of <n> + <engine>
│       each contains: SKILL.md, vendored contracts/ and references/
├── demo-data/
│   ├── scenario-a-happy/           ← <one-line synthetic scenario>
│   └── scenario-b-drama/           ← <one-line synthetic scenario>
└── tests/                          ← only when "bundleTests": true
    ├── sample-test-prompts.csv     ← prompts for the human spot check
    └── <run_tests.py | test_engines.py>
```

Source-only (in the repository, never in the ZIP): `metadata.json`, the top-level `README.md`,
`PACKAGE-NOTES.md` and, unless bundled, `tests/`.

| Field | Value |
|---|---|
| Package name | `<plugin-slug>` |
| Display name | <Display name> |
| Version | <version> |
| Format | Claude plugin (`.claude-plugin/plugin.json`) |
| Skills | <n> |
| Connectors | **<0 — no MCP, no network calls, no external endpoint \| list each connector>** |
| Engines | <n> deterministic Python engines: `<engine_1.py>`, `<engine_2.py>` |
| Runtime dependencies | <Python standard library only \| list> |
| Evaluated ZIP SHA-256 | `<SHA-256>` (<bytes> bytes, <file count> files) |

The evaluated bytes are filed under `Evaluation/<version>/<plugin-slug>.zip`. Do not create the
plugin-folder-level distributable until the human gate clears. The intended distributable name is
`<plugin-slug>-plugin-v<version>.zip`, and it must be copied byte-identical from the evaluated ZIP
only after the tracker's publish gate reads PASS and the owner decision is `Publish`.

---

## 2. The <n> skills

<!-- guidance: One bold paragraph per skill, in chain order: "**<step> · `<skill>` — <one-line
role>.**" then what it reads, what it produces, which engine it runs and what it never does. End
with a "Why they don't compete" paragraph that quotes the unresolved-conflict count from the full
report and explains the "Do NOT use ... use X" deferrals. -->

They run as an ordered chain. Each skill handles one stage, preserves provenance and hands the
contract payload forward. No skill silently does another skill's job.

**1 · `<skill-1>` — <role>.** <Reads ...; produces ...; never ...>

**<n> · `<skill-n>` — <role>.** <Reads ...; produces ...; always marked DRAFT pending ... review.>

**Why they don't compete.** <Deferral approach.> The <version> conflict scan reports
**<n> unresolved conflicts**.

---

## 3. Contract, references and engines

<!-- guidance: Name the contract file and what it carries. Give the stage table. List each reference
file and what rule set it defines, and say whether the rules are illustrative and must be replaced
before production. List each engine with its path and job. Close with the engine/LLM split: what
the model does and everything it must not do. -->

There is no endpoint to configure. The integration surface is the shared contract plus deterministic
engines.

**The contract — `contracts/<contract-file>.json`.** <What it carries across all hops.>

| Stage | Skill | Primary blocks |
|---|---|---|
| <Stage> | `<skill>` | `<block[]>`, `<block{}>` |

**The reference rules.**

- `references/<rule-file>.md` defines <...>. <State if illustrative.>

**The engines.**

- `skills/<skill>/scripts/<engine>.py` — <job>.

The model extracts, orchestrates and writes cited prose. It does **not** <score, decide, clear,
approve, send, or fill missing facts by judgment — list the plugin-specific actions>.

---

## 4. Boundaries

<!-- guidance: This is the guardrails and data-handling section. State the draft-first stance, list
every action the plugin never performs, and describe fail-closed handling (what is held, what
escalates, what the default disposition is). Include the untrusted-data rule for prompt injection. -->

This is a draft-first <purpose> plugin. It helps <roles> <outcome>; it never performs the
<publication | approval | write-back> action.

It **does not**:

- <send, post, upload or share ...>;
- <approve, clear or waive ...>;
- <update a system of record ...>;
- treat a claimed approval from a senior person, client contact or legal as evidence;
- follow instructions found in source data; every field is untrusted data.

<Fail-closed statement: what is held for human review rather than treated as clear.>

---

## 5. Data it needs

<!-- guidance: List the source records a firm must bring, mapped to the contract, including the
citation each record needs. Then describe each synthetic demo scenario in one paragraph: what is
expected to pass, what is expected to be held, and why. Do not name real organisations or people. -->

Bring source-backed records that can be mapped to the contract:

- <source record>;
- source citations for every <record type>.

The demo scenarios provide synthetic examples only:

**`scenario-a-happy` — <title>.** <Expected outcome.>

**`scenario-b-drama` — <title>.** <The trap, and which engine rule catches it.>

---

## 6. Adapting it to a firm

<!-- guidance: Keep these six subsections; add plugin-specific ones if needed. -->

#### Map firm data to the contract

Do not rewrite the workflow first. Start with `contracts/<contract-file>.json` and map each source
system to the contract blocks. Keep citations and confidence values because downstream gates depend
on them.

#### Replace the illustrative rules

<Which reference files are demo summaries; who must supply controlled policy text; update engines to
mirror the rule sections so skill prose and engine constants never diverge.>

#### <Plugin-specific data-handling rule>

<For example: keep restricted records out of reusable prose, or keep sensitive records
need-to-know.>

#### Re-vendor every shared file after edits

The contract and reference rules are vendored into every skill. After changing the master copy, copy
it to all <n> skills and run the shared-copy checker.

#### Regenerate expected outputs after engine changes

After any engine change, regenerate both demo scenarios' expected outputs and rerun the bundled
tests before packaging.

#### Re-evaluate the exact ZIP

Cowork evaluates a ZIP, not a source folder. File the exact evaluated ZIP under
`Evaluation/<version>/`, record its SHA-256, and only promote that same byte sequence after the
human gate clears.

---

## 7. Evaluation history

<!-- guidance: One row per evaluated version, oldest first, including Blocked and No-ship runs.
Evidence summary quotes the archived reports: skills at floor, behavioral pass/total and percentage,
WEAK and FAIL counts, trust and safety held/total, security result, unresolved conflicts, the
blocker classes, and the SHA-256. -->

| Version | Automated verdict | Evidence summary | Publication status |
|---|---|---|---|
| <version> | **<verdict>** | <summary>. SHA `<SHA-256>`. | <Do not publish \| Automated Ready; human gate pending \| Published <date>> |

---

## 8. Validation status — <version>

**Verdict: <verdict>.** Evaluated <YYYY-MM-DD> on the exact ZIP filed in `Evaluation/<version>/`.

| Check | Result |
|---|---|
| Skill health | **<n> of <n>** clear their launch floor |
| Per skill | <skill> <score>/<floor> · <skill> <score>/<floor> |
| Behavioral | **<pass> of <total>** cases pass · <n> WEAK · <n> FAIL · avg output quality **<x>/5** · <n> guardrail failures |
| Trigger consistency | **<n> of <n>** should-trigger cases at 3/3 · **<n> of <n>** negative cases stayed quiet |
| Trust and safety | **<held>/<total>** held · <n> violated |
| Security scan | <Clean \| findings by severity> |
| Coexistence | **<n> unresolved conflicts** |
| Package integrity | <ZIP layout and member check from the report> |
| Run label | `<Cowork run label>` |
| Run currency | Run on the evaluated artifact, SHA `<SHA-256>` |
| Evidence | `Evaluation/<version>/recommendations.html`; `Evaluation/<version>/behavioral-test-report.html`; `Evaluation/<version>/plugin-health.html`; `Evaluation/<version>/<plugin-slug>.zip` |

**Human-gate status: <Not started | In progress | Passed <date> | Failed>.** The tracker workbook in
this folder is prepared with <n> prompts, including every critical-path prompt. Both reviewers run
every prompt in the tracker. Publication can proceed only after the workbook publish gate evaluates
to PASS and the owner decision in the tracker is `Publish`.

**Distributable status: <Not yet promoted | Promoted <date>>.** After a `Publish` decision, copy
the evaluated ZIP byte-identical from `Evaluation/<version>/` to
`<plugin-slug>-plugin-v<version>.zip` and verify its SHA-256 is `<SHA-256>`. Any rebuild means
re-evaluation.

**Install and smoke test.**

<!-- guidance: Steps a deployer follows after promotion. Keep them generic to Cowork. -->

1. Download `<plugin-slug>-plugin-v<version>.zip` from the plugin folder and confirm its SHA-256.
2. Import the ZIP into Cowork as a plugin. Confirm the importer treats the single top-level folder
   as the plugin root and lists all <n> skills.
3. Run scenario A end to end and confirm the output matches the expected files.
4. Run one draft-first prompt (for example "send this") and confirm nothing is sent.
5. <Connector or configuration steps, or "No connectors to configure.">

**Required follow-ups before publication.**

- Two independent human testers run every prompt in the tracker. Critical-path prompts it must
  contain: <list the critical-path prompts by name>.
- <Policy owner confirmation of illustrative rules, if any.>
- The accountable owner records `Publish` in the tracker.
- Before promotion, perform an artifact identity check against the evaluated ZIP SHA-256.

**Known limitations / next-version backlog.** Non-blocking findings from the <version> report.
Nothing below blocked the verdict. <If the verdict is not Ready, list blockers first under a
separate "Blockers to fix in <next version>" heading, then every WEAK.>

- <finding, impact, intended fix>

---

## Document change history

| Date | Version | Change |
|---|---|---|
| <YYYY-MM-DD> | <version> | <Created after <verdict> evaluation \| human gate passed \| promoted> |

*Package maintained by <owning team or role>. Evidence in `Evaluation/<version>/`. Reports are
generated by the plugin evaluation built into Cowork.*
