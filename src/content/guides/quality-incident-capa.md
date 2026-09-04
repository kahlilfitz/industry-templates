# Quality Incident & CAPA

Picks up where **Quality Inspection & Nonconformance** leaves off: an NCR is open, and someone
has to take it through root cause to a closed CAPA that will survive an audit.

It reads the incident, complaint and inspection data, establishes root cause with a structured
method, builds corrective *and* preventive actions with mandatory effectiveness checks,
validates closure readiness as an explicit gate, and drafts the 8D report cited to the clause.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `ncr-intake` | Consumes the NCR payload (including directly from the Quality Inspection template) |
| 2 | `root-cause-analyze` | Establishes root cause — Pareto plus a structured why-chain (deterministic) |
| 3 | `capa-build` | Builds corrective and preventive actions with mandatory effectiveness checks |
| 4 | `closure-check` | The governance gate: is this actually ready to close? |
| 5 | `eightd-draft` | Drafts the 8D / CAPA report, cited to the clause |

## The case that shows why it exists

The supervisor's email carries the pressure: *operator error, retrain, close by Friday.*

The data disagrees. Operator error has four rows — but calibration drift has six, across
**three part numbers and two machines**. And even if operator error ranked first, the rules
reject a human-error root cause when the issue has recurred: recurrence means the system
allowed it, not that someone was careless.

The engine finds a systemic calibration-drift cause traced to a missing recall gate, requires a
preventive action across the affected scope, and refuses to mark the CAPA closure-ready while
verification evidence is outstanding.

A naive CAPA closes on retraining. This one will not.

## What you bring

The open NCR (or the payload handed over from the Quality Inspection template), complaint data,
and inspection results.

## Boundaries

Draft-first: the template takes an open NCR to *closure readiness*. Nothing is filed and nothing
is closed by the template — a quality engineer signs off.

Grounded in ISO 9001:2015 §10.2, IATF 16949, 8D and AIAG-VDA FMEA — see `references/`.

## Skills in this package

- **capa-build** — Builds corrective and preventive actions with mandatory effectiveness checks from the verified root cause, using the deterministic capa_logic engine. Use when the user says "build the CAPA", "what actions do we take", "corrective actions please", or after root-cause-analyze in a CAPA run.
- **closure-check** — Validates CAPA closure readiness against the closure rules - the explicit Govern step of this plugin. Use when the user says "can we close this CAPA", "is the 8D ready to close", "close it out", or before any closure recommendation.
- **eightd-draft** — Drafts the 8D / CAPA report from the contract payload, cited to the clause and rules, with open blockers leading. Use when the user says "draft the 8D", "write the CAPA report", or after closure-check in a CAPA run.
- **ncr-intake** — Reads the open NCR (the mfg.quality-inspection.v1 payload handed off by the Quality Inspection plugin), complaint log and inspection data into the mfg.quality-incident-capa.v1 contract. Use when the user says "open a CAPA for NCR <id>", "work the nonconformance", "start the 8D", or when a CAPA run begins.
- **root-cause-analyze** — Establishes root cause with a structured method - Pareto over the complaint window, then an evidenced 5-Why chain - using the deterministic pareto and rca_tree engines. Use when the user says "what's the root cause", "run the 5-why", "why does this keep happening", or after ncr-intake in a CAPA run.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/quality-incident-capa/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/quality-incident-capa/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
