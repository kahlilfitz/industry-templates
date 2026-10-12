# Confidentiality & Sanitisation Rules - Engagement Closeout
Deterministic rules consumed by `closeout_core.py` (run by `asset_identify.py`, `lesson_cluster.py`, `sanitize_check.py` and `record_check.py`). These are illustrative operating summaries; replace them with controlled firm policy and client terms before production use. Engines cite sections by number, and constants mirror this file.

## 1. Client-identifying material
### 1.1 Direct identifiers
Client names, logos, email domains, project codenames that are known outside the team, site names, account IDs and screenshots with visible tenant or workspace names are not reusable outside the engagement boundary without explicit approval. An asset that carries them is held as `HOLD_REDACTION_REQUIRED` until they are removed or approved.
### 1.2 Specific descriptors
Sector and geography descriptors may be reusable only when broad enough that they do not identify the client alone or in combination. Narrow descriptors are treated as aggregation-risk tokens (#5, `HOLD_AGGREGATION_RISK`).
### 1.3 Client-specific configuration
Configuration, routing, org-design or data artefacts built for one client (marker `client_specific_configuration`) are HELD as `HOLD_REDACTION_REQUIRED` until the client-specific content is removed, whatever the asset's reuse score.

## 2. Named individuals and personal data
### 2.1 Named people
Named individuals, personal contact details and role-plus-name references are personal data. They must be removed or replaced with role-level descriptions before any knowledge record leaves the engagement boundary; until then the item is held as `HOLD_PERSONAL_DATA_REWRITE`.
### 2.2 Blame attribution
Retrospective text that assigns fault to a named person is rewritten as a process or role-level lesson. The original wording is held inside the engagement record, not reused, and the item is held as `HOLD_PERSONAL_DATA_REWRITE` until the rewrite is reviewed.

## 3. Commercially sensitive figures
### 3.1 Sensitive figures
Pricing, contract value, revenue, margin, precise staffing/headcount, savings commitments and implementation dates are commercially sensitive when they can reveal scale, timing or terms. Use bands or remove; until then the asset is held as `HOLD_REDACTION_REQUIRED`. Exact figures may also contribute to aggregation risk.

## 4. Third-party and licensed material
### 4.1 Licensed content
Third-party diagrams, vendor screenshots, licensed research, benchmark excerpts and proprietary product configuration details require a rights check. Missing rights evidence means the asset is held as `HOLD_RIGHTS_UNKNOWN`.
### 4.2 Named third-party products
A named third-party product can be individually acceptable, but when paired with sector, geography, timing or scale it contributes to aggregation risk.

## 5. Aggregation risk
### 5.1 Combination threshold
Individually safe facts can jointly re-identify a client. Four or more distinct tokens across sector, geography, precise headcount, go-live date, named product/vendor, unique architecture, rare operating model or distinctive metric trigger aggregation review.
### 5.2 Group override
When aggregation risk is triggered, every asset participating in the combination is HELD as a group even if each asset passed its individual check. The asset's own finding moves to `HOLD_AGGREGATION_RISK` too, so no finding for that asset still reads as a release candidate.
### 5.3 Recognised aggregation tokens
The recognised tokens are `sector`, `region`, `client_headcount`, `go_live_date`, `third_party_product`, `named_vendor`, `unique_architecture`, `rare_operating_model`, `distinctive_metric`, `generic_operating_model` and `generic_training_pattern`. A token outside this list is never ignored: it counts toward the #5.1 threshold (unnamed) and holds its asset under #7.4.

## 6. Confidence and default disposition
### 6.1 Confidence floor
If the sanitisation engine confidence is below 0.80, the asset or lesson is held for human review as `HOLD_LOW_CONFIDENCE`.
### 6.2 No auto-clearance
The engine may mark an item as a release candidate for practice review, but it never clears publication or external reuse. Default disposition is HOLD until a cited rule and confidence support a narrower candidate state. An asset whose reuse score did not reach the shortlist band is held as `HOLD_NOT_SHORTLISTED`.

## 7. Clearance states
### 7.1 Candidate states
Permitted candidate states are `RELEASE_CANDIDATE_SANITISED` and `INTERNAL_REUSE_CANDIDATE`. Both require human review and retain citations.
### 7.2 Hold states
The engines emit only `RELEASE_CANDIDATE_SANITISED` as a candidate state; `INTERNAL_REUSE_CANDIDATE` is reserved for human reviewers. Hold states are `HOLD_EMBEDDED_INSTRUCTION`, `HOLD_IDENTITY_UNSCREENABLE`, `HOLD_TERMS_UNAVAILABLE`, `HOLD_UNRECOGNISED_MARKER`, `HOLD_PERSONAL_DATA_REWRITE`, `HOLD_RIGHTS_UNKNOWN`, `HOLD_REDACTION_REQUIRED`, `HOLD_AGGREGATION_RISK`, `HOLD_LOW_CONFIDENCE` and `HOLD_NOT_SHORTLISTED`. Finding targets are `asset`, `asset_group`, `lesson`, `screening`, `register` and `engagement`.
### 7.3 Precedence
When several rules apply to one asset, the asset takes the most restrictive state in the order listed in #7.2 (embedded instruction first, not-shortlisted last); every applying reason and citation is kept. De-duplication never lowers a state, and the overall disposition is `HOLD` while any hold, rewrite or escalation is open.
### 7.4 Unrecognised markers and tokens
A confidentiality marker or aggregation token the engines do not recognise holds its asset as `HOLD_UNRECOGNISED_MARKER` and escalates. The unrecognised value is never repeated.
### 7.5 Confidentiality terms unavailable
An empty `confidentiality_terms` list means client terms cannot be checked: every asset is held as `HOLD_TERMS_UNAVAILABLE`, with a `register` finding and an escalation. An absent or non-list `confidentiality_terms` is an input error.
### 7.6 Lesson findings
Each retrospective input that names a person, assigns blame or names the client, and each decision that names the client, gets a `lesson` finding with disposition `rewrite`. Its clusters are marked `rewrite_required`, and the knowledge record lists the evidence ID as held without repeating the source text.

## 8. Embedded instructions and screening
### 8.1 Embedded-instruction screen
Every supplied free-text value (engagement, artifact, asset, decision, retrospective and terms fields, list items and upstream escalations) is screened before any rule reads it, through the shared `steering_guard.py` detector with the closeout hook vocabulary. Each value is screened line by line, then in adjacent line pairs, then with the other fields of its record, with adjacent records of the same list, and as runs of adjacent list items. IDs, marker tokens and sources are screened with `-`, `_`, `.` and `:` read as spaces and are refused on a hit; an ID is also refused when a segment spells a clause word or an imperative or verdict verb (§8.6). A value that trips, or is too long to screen, is replaced with the withheld placeholder and gets a `screening_holds` entry (path, location, detector family, reason, citation); its text is never repeated, never read by a rule and never classified. An asset with withheld text is held as `HOLD_EMBEDDED_INSTRUCTION`; withheld evidence clusters as `unclassified` with an `embedded_instruction` signal.
### 8.2 Rendered-document screen
Before `sanitize_check.py` returns, the knowledge-record skeleton is rendered and screened line by line and in adjacent-line pairs. A hit withholds every supplied value that contributes to those lines (hold location `rendered`), the asset or evidence that carried them is held as `HOLD_EMBEDDED_INSTRUCTION`, and the whole chain is derived again until no rendered line trips.
### 8.3 Client identity
The client name is harvested from the unmodified input before any screening. If the client name itself is withheld, every other field that repeats it or its distinctive first word is withheld as `client_identity`, every asset is held as `HOLD_IDENTITY_UNSCREENABLE`, and the knowledge record gets no drafted context or lesson text.
### 8.4 Supplied markers and placeholders
Input text shaped like a withheld marker is held as `supplied_marker`; it never suppresses a rule. In an intermediate, the exact withheld placeholder is accepted only at a path that carries its own screening hold; an unbound placeholder is an input error.
### 8.5 Knowledge-record draft check
`record_check.py` re-derives the governed payload, writes the deterministic skeleton and checks a filled draft. Every line except the context and lesson slots must match the skeleton exactly. Each slot holds one line of generalized prose and is refused for: embedded instructions (alone or with the next line), withheld markers or slot brackets, the client name or descriptor, a sector-and-region pair, dates, the headcount, third-party products, named people, held asset or evidence IDs and held titles, copied stage guidance, or copied source wording (any six-word run of a longer source value, or the whole normalised phrase of a source value under six words; single IDs and structural tokens such as `n/a` or `none` are ignored).
### 8.6 Render policy
Supplied titles and citations are rendered into the governed record and the skeleton, so they render only in a positive allow-shape, whether or not the detector trips. A title is a short noun phrase (at most 10 words and 80 characters) with no clause word, no imperative or verdict verb and no verdict phrase such as "cleared for" or "as is". A citation is a source path or document ID (no spaces; it carries a `.`, `/`, `\` or a digit) with an optional `#anchor` and row, line, clause, section, page or named-sheet locators, `;`-separated, at most 160 characters; no path segment, anchor or sheet name may spell a clause word or verb. Any other value is replaced with the withheld placeholder and gets a `screening_holds` entry (location `field`, family `render_shape`); its text is never repeated. The record keeps the field: a withheld asset title is flagged `title_withheld: true` and the asset is held as `HOLD_EMBEDDED_INSTRUCTION`; a lesson with a withheld citation is flagged `citation_withheld: true`; the skeleton shows `title_withheld` or `citation_withheld` with the record ID in place of the text.
