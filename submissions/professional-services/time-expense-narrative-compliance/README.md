# Time & Expense Narrative Compliance

For consultants, billing coordinators and engagement managers who need time-entry narratives that can survive pre-bill and client guideline review.

The package builds a cited activity packet, drafts grounded narratives, maps them to the client's billing-code structure, then runs an explicit **Govern** step against billing guidelines: block billing, prohibited terms, vague wording, required detail, non-billable activity, duplicate meetings, increments, code mismatch and missing time. Govern is explicit because narrative compliance is a determination, not a style preference.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `activity-pull` | Builds a cited packet from enabled, engagement-scoped sources and records every privacy exclusion |
| 2 | `narrative-draft` | Drafts missing narratives and offers grounded rewrites beside preserved existing text |
| 3 | `code-map` | Maps unambiguous entries to phase/task codes and holds conflicting activity as `UNMAPPED` |
| 4 | `guideline-check` | Determines compliance using deterministic rules and verbatim, cited flags |
| 5 | `exception-report` | Writes a local draft pre-bill packet; it never sends or submits anything |

## The case that shows why it exists

Scenario B includes entries that read fine at a skim and still fail deterministically:

- A polished 7.5-hour narrative combines three activity classes under one entry, triggering block-billing rejection.
- The same entry uses prohibited/vague phrases like "attention to", "various matters" and "review and revise".
- Two consultants enter the same meeting with the same narrative, so the second is a duplicate meeting exception.
- A plausible submitted task code maps to the wrong phase and is flagged for pre-bill recoding.
- A link to disabled mailbox metadata is excluded from evidence, disclosed, and held for review.
- Three hours of engagement document activity have no matching time entry and appear in the missing-time report.

A naive reviewer may accept the fluent prose; the engine does not.

## Privacy seam

`config/signal-sources.json` is part of the package on purpose. Every engine enforces the narrowest effective policy from that file and the packet: engagement-scoped calendar metadata and engagement-workspace document activity are enabled, while mailbox content and mailbox metadata are off by default. If a skill runs without the plugin-level config, that same narrow default remains the mandatory floor, so a packet cannot enable mailbox access by itself. A `--signal-config` file is applied on top of the plugin config and can only narrow it. Disabled or unknown signals are removed from evidence and recorded under `provenance.excluded_signals`. A firm can explicitly enable broader sources only with policy approval, matter scoping and user notice.

## Timekeeper scope

Engines return only the requesting timekeeper's activity and time entries. Naming colleagues does not widen the scope. Other people's rows are released only in the engagement-manager team view: the requester must be the engagement manager recorded in the engagement letter, and the user must explicitly confirm the team view, which is passed as a structured `--team-view-confirmation engagement-manager:<engagement_id>` token. The token is compared exactly; surrounding spaces, a changed case or any extra character is an input error with no output. Role is never inferred from what a user says, and every downstream engine re-checks the recorded scope.

## Embedded instructions

Narrative, note, subject, deliverable, purpose, attendee, file-name and citation text is data. Every engine screens it with the shared `steering_guard` detector (vendored byte-identically in each skill's `scripts/`, SHA-256 pinned in `tests/check_shared_copies.py`). The detector works by intent family, not phrase list: text addressed to the assistant, AI or reviewer; verdict steering ("mark this entry compliant"); suppression of the review ("do not flag this entry"); rule override ("ignore the billing guidelines"); authority claims ("already approved by the partner"); scope widening; forwarding; and words that mix Latin with look-alike letters from another script. Billing vocabulary goes in only through its hooks (`signal_policy.STEERING_HOOKS`): verdict words *billable*, *compliant*, *no write down*, *approved for billing*; rule nouns *OCG*, *billing guidelines*, *phase code*; and any e-mail address or URL counts as steering. Each activity and entry is screened as one multi-field record (`scan_fields`), plus its ordered prose-field pairs, so an instruction split across fields is caught; the exception packet screens the client, matter and engagement header fields together the same way. Text too long to screen (over 200,000 characters, alone or joined) is never passed: it is held with the reason "too long to screen for embedded instructions". Flagged text is held for review and withheld from drafts (including a flagged main draft narrative that reaches guideline-check), suggested rewrites, citations, missing-time listings and the exception packet (client-billing-guidelines.md #11).

## Engine-result integrity

The code-map and guideline rules live in one shared module, `billing_rules.py`, which ships byte-identically next to `code_map.py`, `guideline_check.py` and `exception_report.py`. Guideline-check recomputes every entry's code mapping and holds an entry whose supplied mapping disagrees (`code_mapping_mismatch`). Exception-report re-runs the guideline rules before rendering. It refuses governed data, and writes no packet, when a recorded verdict or its flags are less severe than the rules', when missing-time items differ, or when summary totals, verdict counts or missing-time hours contradict the line items; the summary it prints is derived from the line items. An entry whose draft was withheld is re-checked on its own timesheet narrative, so a genuine reject relabelled as a hold is refused. Flag details, citations and excluded-signal IDs are rendered from the re-run and `provenance.excluded_signals`, never from supplied text. A forged "compliant" can never hide a reject (client-billing-guidelines.md #13).

## Input validation

Every engine checks every field it reads before it acts (`signal_policy.validate_packet`, shared byte-identically across the skills). A wrong JSON type (for example `"false"` for a boolean, `{}` or `123` in a list of strings, or `null` where a value is required), a missing required field (including a missing or `null` top-level `period`, or a period whose start is after its end), or an unrecognised enum value such as an unknown verdict, severity or draft status is an input error. The engine writes no output and the error names the field, never the value. Nothing is coerced through truthiness: the team-view confirmation must be a real boolean plus the exact token, so `"true"` or `"yes"` never releases a colleague's rows. A file that is not valid UTF-8 is an input error at every engine, never a traceback. Raw exports are held to the same rule: hours must be plain decimals (`nan`, `inf`, `1e1` and negatives are rejected), dates must be valid `YYYY-MM-DD`, times must be `HH:MM`, and rows must have one cell per column. Open vocabularies fail closed: an unknown document activity type or workplan class maps to `UNMAPPED` and is held for review.

## What you bring

Client billing guidelines, engagement-letter billing terms, task/phase code structure, engagement calendar metadata, document activity logs, existing timesheet entries, prior accepted narratives, WIP/pre-bill records and the firm's configured signal policy.

## Boundaries

Draft-first. It does not submit time, approve a pre-bill, alter WIP balances or bill a client. It does not handle expense reports, receipts or travel claims. Every skill follows the same recipient rule: drafts go only to the internal billing coordinator or engagement manager, never the client or any external address. If asked to share something, it prepares a draft, shows the internal recipients and content, and waits for explicit confirmation; if the internal recipient is unknown, it asks rather than guessing or looking one up. Exception-report owns refusals to submit time or approve a pre-bill.

The release bundle includes `tests/run_tests.py`, `tests/check_shared_copies.py` and the human spot-check prompt set so evaluators can reproduce the packaged engines and verify shared-file integrity.
