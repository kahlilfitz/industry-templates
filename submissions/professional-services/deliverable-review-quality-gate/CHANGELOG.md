# Changelog

## 1.0.1 - 2026-10-01

- Fail closed for missing `evidence_set`, missing `criteria.criteria_sections` and missing `deliverable.required_language`; missing is no longer treated as an empty clean register.
- Kept assertion mapping evidence-linked only: an assertion with no linked evidence IDs or no matching evidence index item is `unsupported`, never supported by fallback evidence.
- Added recipient ambiguity and third-party reliance-language checks so missing/ambiguous recipients or named third-party users hold with release blockers.
- Added G8 data-as-data tripwires for embedded approval, waiver, "do not flag", URL/email forwarding and policy-override text, including Unicode format-character evasions. Patterns target text addressed to the reviewer/assistant or steering this review, so ordinary deliverable prose about AI, reviews or reporting does not raise a false release blocker; both an attack set and a benign set ship as regression checks.
- Preserved tracker-only prior review closures as findings when the current deliverable fix is absent.
- Hardened deterministic engines with clear `InputError` messages, `--generated-at` timestamp pinning, LF JSON output and version `1.0.1` provenance.
- Changed positive review-status wording away from "cleared/ready" states while preserving `not_ready_for_release` for blocker cases.
- Added stdlib regression tests for both golden scenarios and negative fixtures, plus a shared-copy drift checker.
