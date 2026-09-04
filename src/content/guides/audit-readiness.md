# Audit Readiness

For the quality manager six weeks out from a surveillance audit who needs to know, honestly,
where the gaps are — while there is still time to close them.

It maps the audit scope to the standard's clauses, gathers the evidence register and checks it
for completeness, validates each piece of evidence against what the clause actually requires,
flags every gap with a severity, and drafts the readiness pack with owners and actions.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `scope-map` | Maps the audit scope to the standard's clauses (deterministic) |
| 2 | `evidence-gather` | Gathers the evidence register and checks completeness |
| 3 | `gap-check` | Validates evidence against clause requirements and grades each gap (deterministic) |
| 4 | `readiness-pack` | Drafts the readiness pack with gaps, owners and actions |

The gap check is the core of this template, not a wrapper around a document count.

## The case that shows why it exists

"We passed last year and the folder is full." Three majors are hiding in the full folder:

- The **management review minutes** are dated more than 13 months before the audit. Stale.
- The **internal audit** covers production and quality — but maintenance just entered scope, and
  has no coverage.
- An **inspector has been active since June with no training record**.

A naive check counts documents and passes. This one checks dates, coverage and people, and
returns *not ready* with three majors, each with an owner and a produce-the-evidence action.

Gaps close with evidence, not with wording. The template will not let a gap be written away.

## What you bring

The audit scope and standard, your evidence register, and the underlying records — management
review minutes, internal audit reports, training records, calibration records.

## Boundaries

Draft-first: the output is a readiness pack. Producing the missing evidence is human work, and
the template says so rather than papering over it.

Grounded in ISO 9001, IATF 16949 and ISO 19011 — see `references/`.

## Skills in this package

- **evidence-gather** — Builds the evidence register for the mapped clauses from the uploaded QMS exports and document indexes. Use when the user says "gather the evidence", "what do we have on file", "build the evidence register", or after scope-map in a readiness run.
- **gap-check** — Validates the evidence register against clause requirements and flags gaps with severity - the explicit Govern step and the core work of this plugin, via the deterministic gap_check engine. Use when the user says "are we ready for the audit", "check for gaps", "will we pass", or after evidence-gather in a readiness run.
- **readiness-pack** — Drafts the audit-readiness pack - verdict, gaps with owners and actions, clause map, evidence index - from the contract payload. Use when the user says "draft the readiness pack", "prep the audit binder", or after gap-check in a readiness run.
- **scope-map** — Maps the audit scope to the standard's clauses and required evidence types with the deterministic clause_map engine. Use when the user says "we have an audit coming", "map the audit scope", "what clauses apply", or when an audit-readiness run begins.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/audit-readiness/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/audit-readiness/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
