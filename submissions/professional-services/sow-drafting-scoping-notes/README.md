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
