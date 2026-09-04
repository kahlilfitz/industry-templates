# Quality Inspection & Nonconformance

For the quality inspector or engineer who has an inspection lot in front of them, a
measurement export, a drawing, a certificate of conformance — and a supplier waiting on a
release decision.

This template reads all of it, compares every actual against its tolerance, grades each
defect by severity and disposition, and hands back a drafted nonconformance report where
every call is cited to the clause or drawing note it came from.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `spec-ingest` | Reads part specs, drawings, inspection plans, CoC and measurement exports into the `mfg.quality-inspection.v1` contract |
| 2 | `tolerance-check` | Compares actuals against tolerance, computes per-characteristic stats, flags out-of-tolerance and *marginal* results, cross-checks the certificate against measured reality |
| 3 | `defect-grade` | Grades severity and recommends a disposition — use-as-is, rework, scrap, return-to-vendor, hold-for-review |
| 4 | `ncr-draft` | Drafts the NCR and inspection summary, every determination cited |

Numbers come from deterministic Python engines (`tolerance_check`, `defect_grade`); the model
does extraction, orchestration and the cited prose. It never invents a severity or a
disposition — it quotes the engine.

## The case that shows why it exists

In the second demo scenario, everything invites a release. Dimensions all pass. The finish
miss looks cosmetic. The certificate explicitly certifies the finishing process. The supplier
is calling and the quality engineer is out.

Three traps are sitting in the documents:

- **Drawing NOTE 9** makes surface finish *fatigue-critical*. Ra 1.72 against a 1.6 maximum is
  not cosmetic — it is a critical hold pending design authority.
- **The certificate contradicts the measurements.** Measurements govern. That is a supplier
  corrective-action candidate, not a reason to release.
- **Flatness at 0.096 of 0.100** is legal but marginal — it belongs on a watch list, not on
  the defect list.

A naive review releases the lot on the certificate. The rules engine holds it.

## What you bring

The part spec or drawing, the inspection plan, the measurement export (CMM CSV or similar),
and the certificate of conformance if you have one. Raw, as they arrive — the demo scenarios
include an inspector's email and a drawing-excerpt PDF precisely so the messy path is
exercised.

## Boundaries

Draft-first: nothing is filed, sent, or written back to a quality system. The template ends at
NCR creation and hands off to **Quality Incident & CAPA** for root cause and corrective action.

Grounded in ISO 9001 and the disposition rules in `references/` — replace those with your own.

## Skills in this package

- **defect-grade** — Grades each out-of-tolerance characteristic by severity and recommends a disposition (use-as-is / rework / scrap / return-to-vendor / hold-for-review) using the deterministic disposition rules engine. Use when the user says "grade the defects", "what disposition?", "how bad is it?", "can we ship it?", or after tolerance-check finds any out-of-tolerance characteristic.
- **ncr-draft** — Drafts the nonconformance report (NCR) and inspection summary from the graded contract payload, with every determination cited to the spec and rules. Use when the user says "draft the NCR", "write up the nonconformance", "inspection summary please", or after defect-grade completes with defects.
- **spec-ingest** — Reads part specs, drawings, inspection plans, certificates of conformance and measurement exports for an inspection lot, and normalizes them into the mfg.quality-inspection.v1 contract inputs. Use when the user says "clear this inspection lot", "load the inspection results", "read the spec for part <PN>", "review lot <LOT-ID>", or when an inspection lot review begins.
- **tolerance-check** — Compares actual measurements against spec tolerances for an inspection lot, computes per-characteristic statistics, flags out-of-tolerance and marginal characteristics, and cross-checks certificate claims against measured reality - deterministically. Use when the user says "check tolerances", "compare against spec", "any out-of-spec?", or after spec-ingest completes in a lot review.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/quality-inspection/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/quality-inspection/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
