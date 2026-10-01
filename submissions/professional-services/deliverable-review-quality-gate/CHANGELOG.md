# Changelog

## 1.0.2 - 2026-10-01

- T&S `review-packet/ps-third-party`: removed the raw `{{contract_payload}}` appendix from the packet template and added an external-recipient hold so user-supplied recipients outside `deliverable.intended_recipients` cannot be accepted for draft routing.
- L1: `gate_check.py` now evaluates assertion-level `scope_aligned=false` against `quality-gate-criteria.md #3.1` instead of ignoring the contract field.
- L2: `assertion_map.py` now ranks unsupported definitive conclusions as `release_blocker` under `severity-rules.md #1.1`, covering scenario B B-002.
- L3: `assertion_map.py` now selects best evidence by assertion-class relevance before confidence and cites every linked evidence item, so B-002 uses EV-B2 as the support sample while still citing EV-B3.
- L4: `gate_check.py` now derives G2 disclaimer and G8 embedded-instruction locations from payload/prior-finding/assertion locations rather than hard-coded p2/p1 defaults.
- L5: `gate_check.py` now holds when `client_data_handling`, `brand_checks`, `licensed_content` or `prior_findings` registers are missing instead of treating absence as clean.
- Non-blocking report items: documented unpaginated-source handling, clarified ingest ownership for `required_disclaimer_type`, `scope_aligned` and `client_data_handling` (default `unknown`), corrected criteria-retrieve's retrieve-only example and shipped §8 floor check, documented how gate-check creates `assertion-mapped.json` when available upstream, reordered the packet template to ranked findings before gate summary, removed the duplicate G3 sample-limitation finding, and moved scenario B disclaimer findings to PR-B1's p12 location.

## 1.0.1 - 2026-10-01

- Fail closed for missing `evidence_set`, missing `criteria.criteria_sections` and missing `deliverable.required_language`; missing is no longer treated as an empty clean register.
- Kept assertion mapping evidence-linked only: an assertion with no linked evidence IDs or no matching evidence index item is `unsupported`, never supported by fallback evidence.
- Added recipient ambiguity and third-party reliance-language checks so missing/ambiguous recipients or named third-party users hold with release blockers.
- Added G8 data-as-data tripwires for embedded approval, waiver, "do not flag", URL/email forwarding and policy-override text, including Unicode format-character evasions. Patterns target text addressed to the reviewer/assistant or steering this review, so ordinary deliverable prose about AI, reviews or reporting does not raise a false release blocker; both an attack set and a benign set ship as regression checks.
- Preserved tracker-only prior review closures as findings when the current deliverable fix is absent.
- Hardened deterministic engines with clear `InputError` messages, `--generated-at` timestamp pinning, LF JSON output and version `1.0.1` provenance.
- Changed positive review-status wording away from "cleared/ready" states while preserving `not_ready_for_release` for blocker cases.
- Added stdlib regression tests for both golden scenarios and negative fixtures, plus a shared-copy drift checker.
