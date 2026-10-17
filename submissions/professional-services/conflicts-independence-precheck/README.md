# Conflicts & Independence Pre-Check

For the QRM analyst, conflicts team or engagement partner trying to decide whether a pursuit can even move to a formal review window.

This template resolves the prospective client and its corporate family, searches client, matter, adverse-party and independence registers, applies deterministic conflicts and independence rules, and drafts a proposed clearance memo or escalation packet for a human reviewer. It is deliberately a **pre-check and evidence assembly tool, never a clearance tool**.

## Boundary: pre-check only

The package never clears a conflict, waives independence, accepts an engagement, approves a pursuit or overrules QRM. Its clean outcome is only: **"no hits found in the registers searched, subject to review"**, with the search scope, date range and entity variants stated in the memo. A human reviewer must adopt, reject or escalate the proposed position.

That disclosure is the package's primary safety control, so the engine derives it rather than trusting it. `registers_searched` is built from the registers the engine actually read, never copied from the input's own claim, and any register the caller supplies that the engine does not cover is reported in `registers_not_searched` and forces hold-for-human-review. A narrower search silently presented as complete is the real false-negative risk in a pre-check, and the clean outcome is unreachable whenever coverage is incomplete.

Reference excerpts in `references/` are illustrative summaries for grounding the demo. They are not reproduced professional-conduct, audit-independence or statutory rules, and must be replaced with controlled firm policy before real use.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `party-intake` | Takes the pursuit record, prospective client, matter description and party list into the shared contract |
| 2 | `entity-resolve` | Resolves legal names, aliases and corporate-family relationships with deterministic matching |
| 3 | `register-search` | Searches client, matter, adverse-party and independence registers using the resolved variants and family IDs |
| 4 | `conflict-classify` | Applies the deterministic Govern rules: conflict type, waiver posture, ethical-wall eligibility and escalation, and attests what was actually searched |
| 5 | `clearance-memo` | Drafts a proposed memo or escalation packet from the cited engine output |

Entity resolution and conflict classification come from Python engines (`entity_resolve`, `conflict_classify`). The model normalizes messy intake text and drafts cited prose. It never decides that a conflict is clear and never downgrades an engine hold.

## The case that shows why it exists

The second demo is built to defeat a naive name-only review.

- The prospective client arrives as **Aster Health Labs**, a trading brand that does not appear in the matter register.
- Corporate-family resolution maps it to **Aster Diagnostics LLC**, a subsidiary of **VegaNova Holdings PLC**.
- VegaNova is the adverse party in a live matter the firm is running for another client, and it is also covered by an illustrative audit-independence restriction for prohibited transaction-valuation services.
- A former-client matter for Aster Diagnostics is still inside the 24-month duty window.
- A separate party, **Kelvin Bio Systems**, lands in the forced-human-review name-match band against **Kelvar Bio Systems Ltd**. The engine refuses to decide either way.

A name-only search returns nothing. The deterministic engines surface the parent-company conflict, the former-client duty and the ambiguous-party hold, then produce an escalation position for QRM review.

## What you bring

Pursuit intake, prospective client and party list, corporate-structure extracts, client and matter registers, adverse-party lists, independence restriction data, prior clearance decisions and firm QRM policy.

## Boundaries

- Draft-first: nothing is written back to a conflicts system, filed, sent or approved.
- Below-threshold confidence holds for human review by default.
- Incomplete register coverage holds for human review and cannot produce a clean outcome.
- Prior clearance decisions are surfaced as non-controlling context and never downgrade a current hit.
- Non-waivable or prohibited-service categories cannot be downgraded by the model.
- Ethical walls are suggested only where the engine marks them eligible; active adversity, audit-independence restrictions, statutory prohibitions and uncertain identity are not wall-only outcomes.
