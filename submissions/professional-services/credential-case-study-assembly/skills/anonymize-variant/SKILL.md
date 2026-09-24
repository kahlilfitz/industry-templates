---
name: anonymize-variant
description: Produces the anonymised credential and case-study variant after `permission-check` refuses naming or flags a descriptor as re-identifying. Use when the user says "make it anonymous", "we cannot name the client", "sanitize this credential", "can we describe them as a top-five insurer?", or after `permission-check` sets `anonymised_variant_required=true`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Anonymize Variant
## Purpose
Create an anonymised draft path whenever naming is not cleared, while preserving the engine's refusal and avoiding re-identification by aggregation.
## When to use
After `permission-check` when `permission_verdict.anonymised_variant_required=true`, or whenever a user asks for anonymous case-study language.
## Inputs
`governed.json` with `permission_verdict`.
## Steps
1. Read `permission_verdict.proposed_descriptor_status`. If it is `reidentifying`, do not use the proposed descriptor.
2. Use only `permission_verdict.safe_descriptor` for the client description when naming is refused.
3. Remove the client name, logo, named people, exact dates, market rank/size claims and unique programme labels unless the engine says they are cleared.
4. Draft the anonymised short, medium and long variants from cleared figures only.
5. Preserve the refused-name rationale and descriptor warning in the clearance appendix.
## Output
An anonymised variant payload inside the credential record, ready for `credential-record`.
## Grounding requirements
Every anonymisation decision cites `reference-naming-permission-rules.md #7`; the safe descriptor must come from `permission_check`.
## Constraints
- The model does not invent a "safe enough" descriptor.
- Do not launder an uncleared figure by rounding or paraphrasing.
- Do not remove the refusal rationale from the final record.
## Escalation / uncertainty
If the business needs a more specific descriptor than the engine's safe descriptor, escalate to legal/reference operations for new written clearance rather than weakening the rule.
