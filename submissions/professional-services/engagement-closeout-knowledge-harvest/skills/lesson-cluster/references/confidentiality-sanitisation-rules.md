# Confidentiality & Sanitisation Rules - Engagement Closeout
Deterministic rules consumed by `sanitize_check.py`. These are illustrative operating summaries; replace them with controlled firm policy and client terms before production use. Engines cite sections by number, and constants mirror this file.

## 1. Client-identifying material
### 1.1 Direct identifiers
Client names, logos, email domains, project codenames that are known outside the team, site names, account IDs and screenshots with visible tenant or workspace names are not reusable outside the engagement boundary without explicit approval. The default disposition is HOLD until removed or approved.
### 1.2 Specific descriptors
Sector and geography descriptors may be reusable only when broad enough that they do not identify the client alone or in combination. Narrow descriptors are treated as aggregation-risk tokens.

## 2. Named individuals and personal data
### 2.1 Named people
Named individuals, personal contact details and role-plus-name references are personal data. They must be removed or replaced with role-level descriptions before any knowledge record leaves the engagement boundary.
### 2.2 Blame attribution
Retrospective text that assigns fault to a named person is rewritten as a process or role-level lesson. The original wording is held inside the engagement record, not reused.

## 3. Commercially sensitive figures
### 3.1 Sensitive figures
Pricing, contract value, revenue, margin, precise staffing/headcount, savings commitments and implementation dates are commercially sensitive when they can reveal scale, timing or terms. Use bands or remove; exact figures may also contribute to aggregation risk.

## 4. Third-party and licensed material
### 4.1 Licensed content
Third-party diagrams, vendor screenshots, licensed research, benchmark excerpts and proprietary product configuration details require a rights check. Missing rights evidence means HOLD.
### 4.2 Named third-party products
A named third-party product can be individually acceptable, but when paired with sector, geography, timing or scale it contributes to aggregation risk.

## 5. Aggregation risk
### 5.1 Combination threshold
Individually safe facts can jointly re-identify a client. Four or more distinct tokens across sector, geography, precise headcount, go-live date, named product/vendor, unique architecture, rare operating model or distinctive metric trigger aggregation review.
### 5.2 Group override
When aggregation risk is triggered, every asset participating in the combination is HELD as a group even if each asset passed its individual check.

## 6. Confidence and default disposition
### 6.1 Confidence floor
If the sanitisation engine confidence is below 0.80, the asset or lesson is HELD for human review.
### 6.2 No auto-clearance
The engine may mark an item as a release candidate for practice review, but it never clears publication or external reuse. Default disposition is HOLD until a cited rule and confidence support a narrower candidate state.

## 7. Clearance states
### 7.1 Candidate states
Permitted candidate states are `RELEASE_CANDIDATE_SANITISED` and `INTERNAL_REUSE_CANDIDATE`. Both require human review and retain citations.
### 7.2 Hold states
Hold states include `HOLD_REDACTION_REQUIRED`, `HOLD_AGGREGATION_RISK`, `HOLD_RIGHTS_UNKNOWN` and `HOLD_LOW_CONFIDENCE`.
