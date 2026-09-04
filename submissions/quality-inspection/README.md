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
