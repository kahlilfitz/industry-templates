# Client Billing Guidelines (illustrative summary)

These excerpts are invented for the gallery package. They summarize the kind of outside-counsel-guideline-style rules a client may apply; they are not copied from any real client, firm, court rule or standard.

## 1. Narrative sufficiency
1.1 A billable narrative must contain at least 12 words of client-facing detail. Shorter narratives are rejectable unless the client guideline expressly allows a code-only entry.
1.2 A narrative must identify the actor's work, the subject, and the client-facing purpose. Missing any element makes the entry needs-review; missing two or more makes it rejectable.
1.3 Narrative prose may be drafted by the model from cited activity signals, but sufficiency is determined only by the rules engine.

## 2. Block billing
2.1 A single narrative over 2.0 hours that combines more than one activity class is prohibited block billing and is rejectable.
2.2 A single narrative at or under 2.0 hours may combine up to two closely related activity classes when the subject and purpose are explicit.

## 3. Prohibited and vague wording
3.1 Prohibited terms are: "attention to", "various matters", "miscellaneous", "work on file", and "general follow up".
3.2 Vague verb phrases are: "review and revise", "work on", "handle", "follow up", and "touch base". A vague phrase is rejectable when no specific subject and purpose cure it.
3.3 The engine reports the matched phrase exactly and cites this section; the model must not paraphrase away the flag.

## 4. Code mapping discipline
4.1 The task code must match the activity class and phase. A plausible but wrong code is an exception because it is recoded or rejected at pre-bill.
4.2 If the submitted code conflicts with the mapped code at confidence 0.80 or higher, the entry is needs-review even when the narrative is otherwise fluent.

## 5. Non-billable activity classes
5.1 Internal staffing, billing administration, time entry correction, training, and internal status meetings are non-billable unless the engagement letter names them as client-approved services.
5.2 Non-billable entries may be retained for WIP hygiene but must not be placed on a client bill.

## 6. Increment and evidence checks
6.1 Time must be rounded to 0.1 hour increments.
6.2 Billed duration may not exceed linked activity evidence by more than 0.2 hours without an explanatory citation.

## 7. Duplicate meeting entries
7.1 Two people may bill the same client meeting only when each narrative states a distinct contribution. Duplicate or near-duplicate narratives for the same meeting are rejectable for all but the first detected entry.

## 8. Missing time
8.1 Engagement-scoped calendar or document activity of 0.5 hours or more with no matching time entry is a missing-time exception.
8.2 Missing time is reported for review; the plugin never creates or submits time automatically.

## 9. Confidence and human gate
9.1 Any compliance determination below 0.75 confidence becomes hold_for_review.
9.2 The engagement manager owns exceptions, write-offs and pre-bill approvals.

## 10. Signal privacy
10.1 Default activity retrieval uses the narrowest range that still works: engagement-scoped calendar metadata and engagement-workspace document activity are enabled; mailbox content is off by default and requires firm policy approval before use.
