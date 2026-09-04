# Engineering Change & BOM

For the change board or design engineer holding an ECR that "looks minor" and needs to know
what it actually touches before anyone approves it.

It reads the ECR, the spec or drawing delta and the BOM, traces impact across the BOM with
where-used, classifies form/fit/function impact, flags interface violations, rolls up document
and inventory dispositions, and drafts the ECN with the affected-item list.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `ecr-ingest` | Reads the ECR, spec/drawing delta and BOM into the contract |
| 2 | `bom-impact` | Traces where-used across the BOM and classifies form/fit/function impact (deterministic) |
| 3 | `standards-check` | Checks the change against drawing standards and design rules |
| 4 | `ecn-draft` | Drafts the ECN with the affected-item list |

## The case that shows why it exists

"Minor tolerance relax, savings already booked, push it through this week." The requester
checked the obvious assembly and it was fine.

Where-used returns a second one — a legacy assembly with an **interface-critical** link, where a
press-fit mate depends on the tight bore the change is relaxing. That escalates the impact class
to *function* with an interface violation. On top of that, the inspection plan for the affected
part is sitting at an obsolete revision, which blocks release outright, and the relaxed
press-fit band breaks a documented design rule.

A naive reviewer approves the minor change. The engines block it, and say exactly why.

## What you bring

The ECR, the BOM, the affected drawings or specs, inventory status, and your document register.

## Boundaries

Draft-first: the ECN is a draft for the change board. No PLM write-back.

Grounded in ASME Y14.5, drawing standards and the design rules in `references/` — replace them
with your own.

## Skills in this package

- **bom-impact** — Traces the change across the BOM with where-used and rolls up form/fit/function impact, interface violations, document updates and inventory disposition - deterministically. Use when the user says "what does this change affect", "run where-used", "impact analysis", or after ecr-ingest in a change run.
- **ecn-draft** — Drafts the engineering change notice with the affected-item list, document updates, dispositions and open requirements from the contract payload. Use when the user says "draft the ECN", "write up the change", or after standards-check in a change run.
- **ecr-ingest** — Reads the engineering change request, spec/drawing delta and BOM export into the mfg.engineering-change-bom.v1 contract. Use when the user says "assess this change request", "work ECR <id>", "what does this change touch", or when an engineering-change run begins.
- **standards-check** — Checks the proposed change against drawing standards and internal design rules, citing each rule applied. Use when the user says "does this meet the design rules", "standards check", "is this change allowed", or after bom-impact in a change run.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/engineering-change-bom/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/engineering-change-bom/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
