# Store Associate Assist

For the store associate on the floor with a customer in front of them and a question that
spans a category no one person can master — product, policy, promotion, procedure.

It takes the question with store, role and department context, retrieves the applicable
policy, product attributes and current promotion, resolves the policy and compares products
deterministically, and returns a cited answer — or a drafted escalation when the answer is
not in scope.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `question-intake` | Takes the question with store, role and department context |
| 2 | `policy-retrieve` | Retrieves the applicable policy, SOP and product sources |
| 3 | `product-compare` | Builds the side-by-side comparison (deterministic) |
| 4 | `promo-check` | Checks the current promotion, price and eligibility (deterministic) |
| 5 | `answer-draft` | Drafts the cited answer or the escalation |

The policy resolution and product comparison come from deterministic engines; the model
retrieves, orchestrates and writes the cited prose.

## The case that shows why it exists

Price-match pressure, with the customer standing there. Three things the documents settle:

- The **exclusion clause outranks the general one** — marketplace and third-party sellers are
  excluded, and the answer cites the clause rather than the general policy.
- The bundle promotion **ended one day before**, and the eligibility test names the failing
  leg with exact dates.
- Price execution stays a manager action, so the draft gives the associate the script *and* a
  manager escalation.

A naive assistant matches the price because "the old manager did". This one cites why not.

## What you bring

Store SOPs and the employee handbook, returns and price-match policy, a PIM or catalog
extract, promotion packs, and planogram notes.

## Boundaries

Answers and drafts only. It never overrides a price, authorises a refund, reserves inventory
or changes a schedule.

## Skills in this package

- **answer-draft** — Drafts the cited answer for the associate - or the escalation when the question is out of scope or below confidence. Use to close every assist run.
- **policy-retrieve** — Resolves the applicable policy clause and checks promotion eligibility deterministically with the policy_resolve engine. Use when the question involves returns, price match, rainchecks, promotions, eligibility, or "what does the policy say", after question-intake.
- **product-compare** — Builds a side-by-side product comparison from the PIM extract with the deterministic product_compare engine. Use when the associate asks "what's the difference between these two", "which should I recommend", or names two SKUs.
- **promo-check** — Answers "is this on promo / does this customer get the deal" using the deterministic three-part eligibility test already computed by policy_resolve. Use for any promotion, discount, or deal-eligibility question.
- **question-intake** — Takes an associate's floor question with store, role and department context into the rtl.store-associate-assist.v1 contract. Use when an associate asks "can a customer return this", "do we price match", "is this on promo", "which of these two should I recommend", or any store policy, product or promotion question.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/store-associate-assist/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/store-associate-assist/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
