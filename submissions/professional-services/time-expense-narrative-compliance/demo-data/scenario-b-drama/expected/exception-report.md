# DRAFT - not sent, not approved

**Pre-bill exception packet** - Orion Advisory Cooperative / Billing Controls Implementation (ENG-SYN-042)

- Prepared for: engagement manager and billing coordinator (review only)
- Period covered by the governed data: 2026-09-14 to 2026-09-18 (entries and activity actually dated 2026-09-14 to 2026-09-18)
- Generated: 2026-09-23T00:00:00Z by exception_report/1.0.13 from guideline_check output (flags quoted verbatim)

## Summary

- Entries: 4 (10.8 h)
- Verdicts: compliant 1, reject 3
- Missing time: 3.0 h across 2 activity signal(s)
- Excluded by signal policy: B-MAIL-001 [client-billing-guidelines.md #10.1]

## Rejects - rewrite or remove before pre-bill

| Entry | Person | Date | Hours | Engine flags (verbatim) |
|---|---|---|---|---|
| TE-B-001 | Morgan Lee | 2026-09-15 | 7.5 | `disabled_source_signal` (hold_for_review): linked signal(s) from a disabled or unresolvable source were excluded and not counted as evidence: B-MAIL-001 [client-billing-guidelines.md #10.1]<br>`required_elements_missing` (reject): missing required elements: actor, purpose [client-billing-guidelines.md #1.2]<br>`block_billing` (reject): 7.5 hours combines 3 activity classes: client_meeting, document_analysis, research [client-billing-guidelines.md #2.1]<br>`prohibited_term` (reject): matched prohibited term 'attention to' [client-billing-guidelines.md #3.1, client-billing-guidelines.md #3.3]<br>`prohibited_term` (reject): matched prohibited term 'various matters' [client-billing-guidelines.md #3.1, client-billing-guidelines.md #3.3]<br>`vague_phrase` (reject): matched vague phrase 'review and revise' with no specific subject and purpose to cure it [client-billing-guidelines.md #3.2, client-billing-guidelines.md #3.3]<br>`vague_phrase` (reject): matched vague phrase 'work on' with no specific subject and purpose to cure it [client-billing-guidelines.md #3.2, client-billing-guidelines.md #3.3]<br>`vague_phrase` (reject): matched vague phrase 'follow up' with no specific subject and purpose to cure it [client-billing-guidelines.md #3.2, client-billing-guidelines.md #3.3]<br>`date_mismatch` (needs_review): entry dated 2026-09-15 links activity from another date: B-CAL-001 (2026-09-14), B-DOC-001 (2026-09-14) [client-billing-guidelines.md #6.2]<br>`evidence_overrun` (needs_review): 7.5 billed hours exceeds 1.1 hours of same-date linked evidence (4.3 hours across all linked dates) by more than 0.2 [client-billing-guidelines.md #6.2]<br>`unmapped_code` (hold_for_review): linked signals point to different codes (client_meeting->DL300, document_analysis->AN200, research->AN220); no code is recommended; submitted DL300 cannot be confirmed [task-phase-codes.md #5.3, client-billing-guidelines.md #4.1]<br>`confidence_floor` (hold_for_review): confidence 0.4 below 0.75 [client-billing-guidelines.md #9.1] |
| TE-B-003 | Jordan Kim | 2026-09-14 | 1.5 | `submitted_code_mismatch` (needs_review): submitted AN220 does not match recommended DL300 [task-phase-codes.md #3.1, client-billing-guidelines.md #4.1, client-billing-guidelines.md #4.2]<br>`duplicate_meeting` (reject): near-duplicate meeting narrative for MTG-ORION-201: similarity 1.0 >= 0.92 with TE-B-002 [client-billing-guidelines.md #7.1] |
| TE-B-004 | Morgan Lee | 2026-09-18 | 0.3 | `minimum_detail` (reject): 7 words < 12 required words [client-billing-guidelines.md #1.1]<br>`required_elements_missing` (needs_review): missing required element: purpose [client-billing-guidelines.md #1.2]<br>`non_billable_activity` (reject): entry is linked to internal/non-billable activity [client-billing-guidelines.md #5.1, task-phase-codes.md #4.1] |

## Held for review

- TE-B-001 (listed under Rejects): also hold_for_review - `disabled_source_signal`, `unmapped_code`, `confidence_floor`; see that row for the verbatim flags and citations.

## Needs review

- TE-B-001 (listed under Rejects): also needs_review - `date_mismatch`, `evidence_overrun`; see that row for the verbatim flags and citations.
- TE-B-003 (listed under Rejects): also needs_review - `submitted_code_mismatch`; see that row for the verbatim flags and citations.
- TE-B-004 (listed under Rejects): also needs_review - `required_elements_missing`; see that row for the verbatim flags and citations.

## Missing time

| Activity | Person | Date | Hours | Subject | Citations |
|---|---|---|---|---|---|
| B-DOC-003 | Morgan Lee | 2026-09-16 | 2.0 | api mapping appendix | raw/document-activity-log.csv row 4, raw/engagement-workplan.csv row 5, client-billing-guidelines.md #8.1 |
| B-DOC-004 | Morgan Lee | 2026-09-17 | 1.0 | migration worksheet | raw/document-activity-log.csv row 5, raw/engagement-workplan.csv row 6, client-billing-guidelines.md #8.1 |

## Privacy exclusions

- B-MAIL-001: linked from TE-B-001 (raw/timesheet.csv row 2); the ID belongs to the 'mailbox_metadata' source, which is disabled in config/signal-sources.json, so that source was not read and the link is not evidence [raw/timesheet.csv row 2, client-billing-guidelines.md #10.1]

## Compliant drafts

- TE-B-002 (Priya Shah, 2026-09-14, 1.5 h): Attended billing controls kickoff meeting with client team to discuss implementation assumptions and next steps.

## Next steps (human decisions)

- The billing coordinator or engagement manager decides every reject, hold and missing-time item (client-billing-guidelines.md #9.2).
- Nothing has been sent, submitted, approved, recoded or used to alter WIP balances. To share this packet, the assistant prepares a draft message, shows the recipients and content, and waits for your explicit confirmation. It is never sent to the client.
