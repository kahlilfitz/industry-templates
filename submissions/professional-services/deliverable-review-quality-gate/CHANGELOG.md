# Changelog

## 1.0.3 - 2026-10-01

Fixes every FAIL, WEAK and should-fix item in the Cowork 1.0.2 evaluation (42/50, Blocked).

- FAIL "required_language = null (register not loaded)": `gate_check.py` `check_missing_registers` now treats an absent **or null** register as not loaded for every register (`criteria.criteria_sections`, `evidence_set`, `client_data_handling`, `brand_checks`, `licensed_content`, `prior_findings`, `required_language`). Each one raises the register-missing hold. A present register of the wrong type is a clean input error, and only an explicit `[]` means "checked, no entries".
- FAIL "client_data_handling blank/null/unrecognised passes clean": `check_client_data_value` whitelists `ok` as the only clean value. `attention` is a G4 must-fix. `breach`, `unknown`, blank, null and any unrecognised value are a G4 release blocker. Every non-`ok` value adds an escalation (`quality-gate-criteria.md #4.3`).
- WEAK "severity_rank traceback on page label 'iv'": `severity_rank.py` `validate_finding` rejects non-integer page/paragraph, non-numeric confidence and malformed locations with a clean input error that tells the user to keep printed labels in `location.label`. Null page/paragraph (register-level findings) ranks last, and a safety net turns any residual malformed input into an error rather than a traceback (`severity-rules.md #3.2`).
- WEAK "G8 misses Cyrillic/Greek look-alikes": the tripwire normalises text with NFKC, then strips format characters, then folds a curated Cyrillic/Greek confusable map to Latin. It also flags words that mix Latin with look-alike letters.
- WEAK "G8 misses paraphrased steering": new reviewer-, QRM- and assistant-addressed patterns cover leave alone, let through, no need to check, skip/ignore/overlook, already confirmed/verified/approved and do not flag. Matching against business prose stays strict. `tests/run_tests.py` ships both an attack paraphrase set and a benign domain-prose set.
- WEAK "citation field not scanned": `collect_scan_text` now scans every string in primary sections, including citations. Only `contract_version` is exempt. Derived sections are scanned on residue only.
- WEAK "'pre-approved by the client board' raises two G8 blockers": bare approval wording ("pre-approved", "approved for release", "already approved") no longer triggers. A trigger now needs an addressee, a self-reference to the document, a reviewer/partner authority, or skip/do-not-flag context.
- WEAK "upstream finding reusing a G8 ID suppresses the blocker": `screen_upstream_findings` ignores upstream findings that use engine-owned IDs or source tags (`GC-`, or `AM-` without `engine:assertion_map`). Spoof attempts raise `GC-G8-engine-id-spoof` (release blocker) plus an escalation. `add_finding` never lets a duplicate ID lower severity (`quality-gate-criteria.md #8.4`).
- Weak output "G8 note counted twice with a placeholder page-1 location": the copy of an assertion in `assertion_mappings` is no longer scanned a second time. G8 locations come from the item's own location; when an item has none, the location is register-level instead of p1.
- Weak output "missing registers produce no escalations": every missing or null register now adds an `escalations[]` entry. Ambiguous recipient lists do the same. Register-missing findings use a register-level location (page/paragraph null, label "Register not supplied (absent or null)") instead of page 1. The contract location schema allows null page/paragraph.
- Description gap: the review-packet template heading now carries the exact label `DRAFT - HUMAN REVIEW REQUIRED`, and the template explains how to render register-level locations without a placeholder page.
- Description gap: the routing hold and the review-packet skill cite reviewing-partner/QRM confirmation under `quality-gate-criteria.md #2.2` (reliance language) and `#4.2` (client-data exposure) instead of "G2".
- Description gap: "can this go to the client?" now triggers gate-check only. deliverable-ingest says "For a release yes/no on already-ingested material, use gate-check."
- Tests: new regression checks cover a null register for each register, client-data values, page labels, look-alike and paraphrase attacks, the benign prose set, citation injection, engine-ID spoofing, single-count G8, template/description wording, version consistency and shared-copy identity.
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
