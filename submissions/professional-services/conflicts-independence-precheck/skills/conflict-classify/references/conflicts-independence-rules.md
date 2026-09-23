# Conflicts & Independence Rules — Illustrative Pre-Check Ruleset

Illustrative summaries for demo grounding only. This file does not reproduce bar rules, audit-independence standards, statutory text or any firm's controlled QRM policy. Replace it with approved policy before real use. Engines cite these sections; constants in `conflict_classify.py` mirror the numbered rules.

## 1. Determination discipline
1.1 The package assembles a first-pass position for human review. It never clears a conflict, waives independence, accepts an engagement or approves a pursuit.
1.2 A clean engine result is phrased only as "no hits found in the registers searched, subject to review" with scope stated.

## 2. Direct adverse representation
2.1 A prospective client or controlled affiliate that is adverse to an existing client in a live matter is a direct-adverse hit requiring QRM escalation.
2.2 Consent-waivable posture depends on firm policy and client consent. The pre-check may identify consent requirements but never grants consent.

## 3. Corporate-family attribution
3.1 Affiliates with ownership or control >= 50% are included in the conflicts search and must be surfaced as family-attribution hits.
3.2 Lower ownership, board control, management control or special-purpose structures may still require review when the evidence indicates influence.

## 4. Former-client duties
4.1 A former-client matter closed within 24 months remains inside the default duty window for substantially related work.
4.2 Older matters may still escalate when confidential information is likely relevant to the proposed work.

## 5. Positional and issue conflicts
5.1 A proposed position materially inconsistent with a current client position in the same forum, transaction or regulatory issue requires review.
5.2 The model may summarize the issue overlap, but the engine classifies the hit type.

## 6. Financial-interest and employment restrictions
6.1 Covered-person financial interests in the prospective client or controlled affiliate require independence escalation.
6.2 Recent employment, officer, director or key-management relationships involving covered persons require independence escalation.

## 7. Audit-independence prohibited services
7.1 Prohibited non-audit services for an audit client or controlled affiliate are non-waivable in this illustrative ruleset.
7.2 Valuation, management decision-making, systems implementation with management responsibility and advocacy services are examples of prohibited categories for the demo.

## 8. Ethical-wall eligibility
8.1 Ethical walls may be recommended only for categories marked wall-eligible by policy and only when confidential information exposure is contained.
8.2 A wall is not sufficient for active direct adversity, prohibited audit-independence services, statutory prohibitions, materially overlapping personnel or information already shared with the pursuit team.

## 9. Confidence floor and human gate
9.1 Any classification, match or source confidence below 0.75 forces hold-for-human-review.
9.2 A human-review entity-resolution band is itself an escalation; the engine must not decide the conflict either way.

## 10. Waiver posture
10.1 Consent-waivable categories may be routed as required-consent recommendations, never as granted consent.
10.2 Non-waivable categories and prohibited-service categories produce an escalation/refusal-position recommendation for human QRM review.

## 11. Output language
11.1 Do not use "cleared", "approved", "no conflict" or "OK to proceed" in generated outputs.
11.2 State search limits: registers searched, date range, entity variants, corporate-family scope and unresolved parties.
