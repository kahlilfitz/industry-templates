# Consumer & Market Insight Synthesis

For insights and category managers sitting on decades of research, panel data and campaign
results spread across PDF, PowerPoint and spreadsheets in dozens of markets — who re-run
studies because nobody can find the prior one.

It retrieves and ranks prior research and panel extracts, compares trends across markets and
periods, flags contradictory evidence rather than smoothing it, checks usage rights, geography
and claim provenance, and drafts a cited insight brief with a provenance record.

Governance is explicit here because rights and provenance decide whether a finding can be used
at all — not just whether it is interesting.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `research-retrieve` | Retrieves and ranks prior research and panel extracts |
| 2 | `trend-compare` | Compares trends across markets and periods (deterministic) |
| 3 | `contradiction-flag` | Flags contradictory evidence instead of averaging it away |
| 4 | `provenance-check` | Checks usage rights, geography and provenance — the Govern step |
| 5 | `insight-brief` | Drafts the cited brief and the provenance record |

## The case that shows why it exists

*"Board deck tomorrow, killer stat, don't overthink the fine print."* The fine print:

- The remembered penetration number comes from a panel whose **licence expired** — unusable
  for any purpose, however well remembered.
- The strongest frequency read is **syndicated internal-only**, so it cannot go in a board
  deck however strong the stat.
- The core metric **contradicts across studies** — down, then up. Both readings go in the
  brief with their methods and dates. No midpoint is invented.

The brief is built on cleared evidence, and the exclusions are named rather than quietly
dropped.

## What you bring

Internal research repositories in PDF, PPTX and XLSX, syndicated panel extracts, approved
social-listening exports, claim libraries and campaign performance reports.

## Boundaries

Synthesis and citation. It does not produce a demand forecast, approve a claim or assert
causal attribution — and it is not a tool for analysing large tabular datasets.

## Skills in this package

- **contradiction-flag** — Surfaces contradictory evidence - studies moving the same metric in opposite directions - rather than a smoothed answer. Use on "do the studies agree", "any conflicting evidence", after trend-compare.
- **insight-brief** — Drafts the cited insight brief with the provenance and usage-rights record attached. Use to close every insight run: "draft the brief", "write it up for the category review".
- **provenance-check** — Checks usage rights, geography and expiry for every retrieved study against the declared use - the explicit Govern step - with the deterministic provenance_check engine. Use on "can we use this externally", "is this stat cleared for the board deck", after trend-compare.
- **research-retrieve** — Retrieves and ranks prior research, panel extracts and campaign results relevant to the question. Use when the user says "what do we already know about <topic>", "find prior research on", "have we studied this before", or an insight request begins.
- **trend-compare** — Compares trends across markets and periods like-for-like with the deterministic trend_compare engine. Use on "how has this trended", "compare markets", "what changed since the last study", after research-retrieve.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/consumer-market-insight-synthesis/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/consumer-market-insight-synthesis/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
