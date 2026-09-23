# SOW Drafting from Scoping Notes

For engagement managers and pursuit leads who need the first SOW draft to start from the
firm's approved language, not from the last similar engagement with all of its hidden
exceptions.

This template turns discovery-call notes and a CRM pursuit record into a structured draft:
scope, deliverables, assumptions, exclusions, milestones and acceptance criteria. It selects
clauses from the approved library, refuses to draft commitments the notes do not support, and
surfaces clause deviations for QRM review before copy-paste history becomes contractual risk.

Governance is explicit here. A deviation from approved clause language is not a writing choice;
it is a risk determination owned by QRM.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `notes-ingest` | Retrieves discovery notes, pursuit record, prior similar SOWs, the approved clause library and the SOW template |
| 2 | `scope-extract` | Runs `scope_extract.py` to structure scope, deliverables, milestones, assumptions, exclusions and thin-input blocks |
| 3 | `clause-select` | Runs `clause_select.py` to select approved clauses from the maintained library and stop if the library is absent or unversioned |
| 4 | `deviation-flag` | Runs `deviation_flag.py` to flag inherited or requested non-standard terms and route partner/QRM/legal review |
| 5 | `sow-draft` | Drafts the SOW and thin-input report from the engine output and the SOW template |

Thin-input calls, clause selection and deviation severity come from deterministic Python engines
(`scope_extract`, `clause_select`, `deviation_flag`). The model extracts from messy notes and
writes cited prose. It never approves a deviation, invents approved clause language, prices the
engagement or commits a delivery date.

## The case that shows why it exists

In the second demo scenario, the pursuit lead provides a prior executed SOW and says "just copy
this one." It looks like the fastest path to a client-ready draft.

That prior SOW quietly carries two one-off concessions:

- A client-favourable limitation-of-liability clause that replaces the approved cap with a
  broader 3x-fees exposure and breach carve-outs.
- An uncapped data-protection indemnity that QRM allowed once for that client only.

The discovery notes sound detailed, but they never establish who supplies test data, what
"acceptance" means, or what plan supports the enthusiastic go-live date. A naive drafter copies
the old language, inserts the verbal date and fills the gaps with optimistic assumptions. The
engines do the opposite: select the approved library clauses, quote the approved alternatives,
flag the inherited non-standard terms as critical QRM/legal deviations, block unsupported
acceptance and go-live commitments, and turn the missing facts into assumptions and exclusions.

## What you have to bring

A maintained, versioned approved clause library; QRM deviation rules; the firm's SOW and MSA
templates; discovery and scoping notes; the CRM pursuit record; relevant prior executed SOWs;
rate card context; and any controlled delivery-method assumptions. The demo data is synthetic
and illustrative only.

If the approved clause library is absent, stale or unversioned, the package degrades to
structured extraction without the Govern step. That is a narrower deployment scope, not a
permission to invent approved language.

## Boundaries

Draft-first: the package drafts to a review-ready state. It does not approve a clause deviation,
price the engagement, commit a delivery date, issue the SOW, update CRM, file anything in a
contract repository or write back to PSA systems. QRM, legal, pricing and engagement partner
decisions stay human-owned.

Grounded in the clause library and QRM rules in `references/` - replace them with your controlled
firm documents before production use.

## Skills in this package

- **clause-select** — Runs deterministic `clause_select.py` after `scope-extract` to select approved clause-library language for the SOW and stop if the approved library is absent or unversioned. Use when the user says "use approved clauses", "which clauses belong in this SOW?", "draft the SOW from our clause library", or after `scope-extract` produces `scope.json`.
- **deviation-flag** — Runs deterministic `deviation_flag.py` after `clause-select` to compare selected approved clauses with requested or inherited prior-SOW terms and produce the QRM deviation summary. Use when the user says "check deviations", "can we copy this prior SOW?", "what needs QRM?", "is this clause approved?", or after `clause-select`.
- **notes-ingest** — Retrieves and normalizes discovery notes, scoping notes, CRM pursuit records, prior similar SOWs, approved clause library extracts and SOW templates before `scope-extract`. Use when the user says "draft the SOW", "turn these notes into a statement of work", "start from this discovery call", "use this pursuit record", or "copy this prior SOW but check it".
- **scope-extract** — Runs deterministic `scope_extract.py` after `notes-ingest` to extract scope, deliverables, milestones, assumptions, exclusions and the thin-input report. Use when the user says "what did we scope?", "what did we not pin down?", "turn these notes into a statement of work", "draft the SOW", or after `notes-ingest` finishes.
- **sow-draft** — Drafts the review-ready SOW, thin-input report and QRM deviation summary after `deviation-flag` using only selected approved clauses and engine output. Use when the user says "draft the SOW", "write the statement of work", "create the SOW package", "show the thin-input report", or after `deviation-flag`.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/sow-drafting-scoping-notes/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/sow-drafting-scoping-notes/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
