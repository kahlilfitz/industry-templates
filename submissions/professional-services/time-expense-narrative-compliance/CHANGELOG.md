# Changelog - time-expense-narrative-compliance

## 1.0.3 - 2026-10-01

Fix release after the canonical, hash-matched v1.0.1 evaluation (`evaluate-time-expense-narrative-2026-10-01`, verdict **Blocked**, archived under `Evaluation/1.0.1`). v1.0.2 was frozen but superseded before evaluation; this release contains every v1.0.2 change plus the fixes below. Contract remains `ps.time-expense-narrative-compliance.v1` (backward-compatible additions only).

### Blocking findings fixed
- **B1 code-map:** every linked signal is now mapped before any non-billable decision. A client meeting linked together with an internal or non-billable call points to two codes, so it maps to `UNMAPPED` at 0.40 with an `unmapped_code` hold (task-phase-codes.md #5.3) instead of NB900 at 0.92.
- **B2 guideline-check:** an entry billing more than 0.2 h with no linked activity evidence now gets a `no_linked_evidence` hold (client-billing-guidelines.md #6.2) and can never be rated compliant. The #1.2 subject check credits only the entry's own linked signals; it no longer falls back to every signal in the packet.
- **B3 signal policy (SEC-1):** `config/signal-sources.json` (or, stand-alone, the narrow default) is always applied. `--signal-config` is an additional policy that can narrow but never widen or replace it (most restrictive wins), in every engine including activity-pull. Provenance now labels a default run `config/signal-sources.json` and an override `--signal-config <file> (additional)`.
- **B4 injection tripwire (SEC-2):** `embedded_instruction` now also catches reviewer- or AI-addressed notes ("Note to AI", "Hey assistant", "Copilot should"), approval and waiver claims ("the client has waived the guidelines", "rules are suspended"), forward/send/export requests, and any e-mail address (including `[at]`/`[dot]` obfuscation) or URL. It inspects the narrative, the original narrative, notes, suggested rewrites and linked activity subjects/deliverables after stripping Unicode format characters. Exception-report never lists a flagged entry under "Compliant drafts".

### Non-blocking findings fixed
- Billing-hygiene activity now maps to BH910 (task-phase-codes.md #4.2); BH910 is treated as non-billable.
- The exception-report period caveat compares the requested period with the dates actually present in the entries and activity, not only the declared period.
- SKILL.md wording updated for code-map (mixed classes, BH910), guideline-check (zero-evidence hold, broader tripwire, additive `--signal-config`) and exception-report (actual-date caveat).

### Tests
- `tests/run_tests.py` grows from 50 to 72 checks: every paraphrased injection from the canonical report plus contact/URL and zero-width variants, a no-false-positive set of ordinary consulting narratives, the meeting-plus-internal-call conflict, NB900/BH910 mapping, the 8.0 h zero-evidence entry, a tampered `--signal-config` through narrative-draft, code-map, guideline-check and activity-pull, narrowing via `--signal-config`, the default provenance label, the actual-date period caveat and "Compliant drafts" exclusion. Each new fixture fails on the 1.0.2 engines.

## 1.0.2 - 2026-09-30 (frozen, superseded before evaluation)

Fix release after the v1.0.1 evaluation (machine verdict Ready / SHIP WITH NOTES). Contract remains `ps.time-expense-narrative-compliance.v1`; all additions are backward compatible.

### Evaluation and packaging
- Opted this submission into test bundling. The release ZIP now contains `tests/run_tests.py`, `tests/check_shared_copies.py` and `tests/sample-test-prompts.csv` without changing packaging for other submissions.
- Kept the current plugin identity and deferred MOS3 store packaging; neither decision is required for the v1.0.2 behavioral fixes.

### Privacy and prompt-injection hardening
- The narrow default is now a mandatory floor whenever the plugin-level signal config is unavailable. A stand-alone skill cannot accept a packet policy that enables mailbox content or metadata.
- Guideline-check strips zero-width format characters before inspection and catches approval/authority variants such as "pre-approved", "already cleared", "no review required" and "must not be flagged".
- Activity-pull, narrative-draft, code-map and exception-report explicitly treat all packet fields as untrusted data and never follow embedded instructions.

### Narrative and report fidelity
- Existing narratives remain unchanged for compliance review. Narrative-draft now emits separately labeled, cited `suggested_rewrites[]`, one per linked activity, so "make this client-ready" is fulfilled without silently replacing user text or hiding block billing.
- Exception-report indexes hold and needs-review flags across every entry, including entries whose overall verdict is reject; subordinate findings no longer disappear behind the worst verdict.
- Missing-time rows no longer inherit the privacy-policy citation from otherwise enabled activity. They retain source/workplan citations and add only client-billing-guidelines.md #8.1.

### Safety and routing
- Exception-report explicitly forbids inventing facts, hours, names, flags or recipients.
- When the internal billing recipient is unknown, the assistant must request the billing coordinator or engagement manager's name/address; it never guesses, performs an unsolicited lookup or adds an external recipient.
- Wording now describes the plugin's read-only boundary as "never alters WIP balances" while retaining the same prohibition on financial actions.

## 1.0.1 - 2026-09-29

Fix release after the v1.0.0 evaluation (verdict STOP). Contract stays `ps.time-expense-narrative-compliance.v1`; all changes are backward compatible.

### Privacy (H1)
- New shared `signal_policy.py` next to every engine. Each engine reads `config/signal-sources.json` and the packet's `signal_config` (most restrictive wins), drops signals from disabled or unknown sources, and records each exclusion in `provenance.excluded_signals` with the client-billing-guidelines.md #10.1 citation.
- Scenario B: `B-MAIL-001` is no longer an activity signal. The timesheet link is kept only to demonstrate exclusion: `activity_pull` never opens the mailbox source, moves the link to `excluded_activity_ids`, and `guideline_check` raises a `disabled_source_signal` hold. TE-B-001 evidence no longer includes the 0.6 h mailbox item.

### Draft-first (H2)
- exception-report: explicit send rule. It produces a draft only, never sends e-mail or Teams messages, and on "send" prepares a draft, shows recipients and content, and waits for explicit confirmation; never to the client. Same draft-first guardrail wording in all five skills.
- New `exception_report.py` writes the DRAFT Markdown packet (no send capability) and adds a period caveat when the requested period differs from the data.

### Narratives (H3, L1)
- "Attended" unless calendar organizer evidence shows the timekeeper organized the meeting ("Led").
- Grammatical template `<verb> <subject> [with <attendees>] to <purpose> [for the <deliverable>].` with no filler. A draft under 12 words stays short with status `needs_review_insufficient_detail` so guideline-check rejects it (#1.1).
- The draft no longer asserts required elements (fixes the draft/compliance actor contradiction); sufficiency is determined only by guideline_check (#1.3).

### Code mapping (L2)
- Linked signals that point to different codes map to `UNMAPPED` at 0.40 with an `unmapped_code` hold (task-phase-codes.md #5.3). No majority vote.

### Guideline check (L3-L7, L9, W3)
- #1.1 under 12 words = reject. #3.2 vague phrase uncured by an explicit subject and purpose = reject.
- #2.2 implemented (<= 2.0 h: at most two classes, and only with explicit subject and purpose).
- #7.1 near-duplicate = difflib ratio or token Jaccard >= 0.92 per meeting.
- Date-consistency flag (`date_mismatch`); evidence overrun uses same-date evidence only.
- Real actor (leading work verb), subject (linked subject/deliverable coverage) and purpose (purpose clause) checks on every entry.
- Embedded instructions in narrative text (for example "ignore the guidelines", "mark this entry compliant", "do not flag") raise an `embedded_instruction` hold and are never obeyed. Pattern set broadened during the v1.0.1 trust & safety run (probe ps-inj-1).
- All engines: `generated_at` is the real UTC time; `--generated-at` pins it for reproducible demo files. Context-managed file I/O; asserts replaced by clear validation errors.
- All generated JSON and Markdown use LF line endings so golden-file reproduction is byte-identical on Windows and Unix.

### Engines and demo data (W1, W2, L8, P2, P3, P5)
- New `activity_pull.py` builds the activity packet from the raw exports, honoring the signal policy, the requesting timekeeper (`--person` or explicit `--all-timekeepers`) and the period.
- Purpose and deliverable now come from a controlled `raw/engagement-workplan.csv`; organizer from the calendar export; engagement identity from the new `raw/engagement-letter-extract.md` (fixes the dangling citation). Purpose is null, never invented, when no source states one.
- Scenario B README corrected ("three activity classes") and lists every expected finding. Both scenarios' `activity.json` and `expected/*` regenerated; `expected/exception-report.md` added.

### Descriptions and packaging (D1, R1, R2, P1, P4, P6)
- All five descriptions rewritten with 4-5 quoted triggers, "Do NOT use for X (use Y)" deferrals and an expense deferral; overlaps resolved ("write up my time" -> narrative-draft, missing time -> guideline-check, pre-bill packet -> exception-report). Added When NOT to Use, Guardrails, Output format and Example sections.
- Plugin name unchanged (rename is an open decision); `expense` removed from keywords; the manifest description states expenses are out of scope in this version.
- Shared copies: `contracts/` and `references/` at the root and `skills/activity-pull/scripts/signal_policy.py` are the sources of truth; `tests/check_shared_copies.py` fails on drift.
- `tests/run_tests.py`: golden-file reproduction for both scenarios plus negative fixtures (disabled-source signal, tampered packet policy, near-duplicate, <= 2 h three-class entry, date mismatch, conflicting-class mapping, injected instruction, unpadded short draft, Led vs Attended, bad input).

### Not in this release (open decisions)
- Plugin rename (e.g. `time-narrative-compliance`).
- MOS3 store packaging (`manifest.json`, `packageMetadata.json`).

## 1.0.0 - 2026-09-23
Initial release.
