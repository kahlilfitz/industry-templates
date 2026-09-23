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

## Skills in this package

- **anonymize-variant** — Produces the anonymised credential and case-study variant after `permission-check` refuses naming or flags a descriptor as re-identifying. Use when the user says "make it anonymous", "we cannot name the client", "sanitize this credential", "can we describe them as a top-five insurer?", or after `permission-check` sets `anonymised_variant_required=true`.
- **closeout-retrieve** — Retrieves the sanitised closeout knowledge record, deliverables, outcome evidence, engagement terms and reference register before Credential & Case Study Assembly begins. Use when the user says "write up this credential", "do we have a case study for this?", "pull the closeout record", "turn this closeout into a credential", or when a credential/case-study request begins. This runs before `credential-draft`.
- **credential-draft** — Matches a closeout record to the credential taxonomy and prepares the structured draft plan before permissions are checked. Use after `closeout-retrieve` when the user says "write up this credential", "draft the case study", "make this proposal credential", or "classify this engagement for credentials"; run before `permission-check`.
- **credential-record** — Drafts the final credential entry and short, medium and long case-study copy after `permission-check` and optional `anonymize-variant`. Use when the user says "write the credential record", "draft the case study", "make the short and long versions", "prepare this for the credentials library", or "do we have a case study for this?".
- **permission-check** — Determines whether the client can be named, whether logo/testimonial use is allowed, which figures are cleared, and whether an anonymised descriptor re-identifies the client. Use after `credential-draft` when the user asks "can we name this client?", "is this case study cleared?", "can we use this quote?", "can this go on the website?", or before any credential/case-study copy is published.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/credential-case-study-assembly/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/credential-case-study-assembly/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
