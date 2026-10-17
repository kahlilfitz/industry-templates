# Credential & Case Study Assembly

For BD, marketing and practice leads who need to capture credentials while an engagement is still fresh, not reconstruct them from memory during a proposal deadline.

This template consumes the sanitised closeout knowledge record produced by **Engagement Closeout & Knowledge Harvest** (`engagement-closeout-knowledge-harvest`), matches the work to the firm's credential taxonomy, checks naming/reference permissions against engagement terms, and drafts a credential record plus short, medium and long case-study copy for review.

The upstream closeout package exposes `ps.engagement-closeout-knowledge-harvest.v1` with a terminal `knowledge_record.downstream_handoff.consumer_template` set to `credential-case-study-assembly`. This package maps that governed knowledge record, its engagement fields, reusable assets, sanitisation notes and cited handoff fields into `ps.credential-case-study-assembly.v1`; it does not inherit permission to publish, quote a client, use a logo or disclose figures.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `closeout-retrieve` | Retrieves the closeout knowledge record, deliverables, outcome evidence, engagement terms, reference register and BD request |
| 2 | `credential-draft` | Runs `credential_draft` to match the work to sector, service line, capability, engagement-size and outcome taxonomy fields |
| 3 | `permission-check` | Runs `permission_check`, the explicit Govern step: naming, logo, testimonial, anonymisation and figure clearance are refused unless the rules permit them |
| 4 | `anonymize-variant` | Produces an anonymised variant whenever naming is not cleared, using only the safe descriptor approved by the engine |
| 5 | `credential-record` | Drafts the credential entry and short, medium and long case-study copy with the clearance record attached |

The model writes the credential and case-study prose. The engines compute the taxonomy match, permission verdicts, figure-clearance states and anonymisation risk; the model never decides that a client may be named or that a figure may be published.

## The case that shows why it exists

In `scenario-b-drama`, everyone assumes the credential is safe: the client's marketing team co-presented at a conference, the partner says "they're fine with it", and the proposal team wants to cite a 60% processing-time cut.

The documents say otherwise:

- The engagement terms contain an express prohibition on naming the client in marketing material.
- The conference consent was event-only, expired, and did not create public case-study rights.
- The 60% figure is a client-supplied internal estimate, not verified deliverable evidence, so it lands in the UNCLEARED bucket.
- A named-individual testimonial has no separate consent record.
- The proposed "anonymous" descriptor combines top-five market position, sector, date and programme type, which re-identifies the client under the aggregation rule.

A naive reviewer publishes the named credential. The Govern engine refuses to name, separates the uncleared figure and flags the anonymised descriptor as unsafe.

## What you bring

A sanitised closeout knowledge record from Engagement Closeout & Knowledge Harvest, the closeout deliverables and outcome evidence it cites, engagement terms/reference clauses, the reference register, the credential taxonomy, prior published credentials, and the BD or marketing request.

## Boundaries

Draft-first: this template drafts and checks. It does **not** publish, approve external use, clear a client name, grant logo rights, approve a testimonial, or assert an unverified outcome figure. Missing permission is a refusal, not an invitation to infer consent.

Grounded in illustrative reference and naming permission rules plus the credential taxonomy in `references/`; replace them with the firm's controlled policy and contract clause library.
