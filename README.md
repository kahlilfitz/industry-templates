# Industry Templates

A gallery of **industry templates** for AI agents — ready-to-install plugin packages that give a
Copilot agent the work of a real role in a real industry, complete with the rules, contracts,
reference documents and demo data that make the work reliable.

**→ [Browse the gallery](https://sravaniseethi.github.io/industry-templates)**

Two industries so far, twenty Microsoft 365 Copilot **Cowork** plugins:

- **Manufacturing** — quality, maintenance, EHS, supply chain, planning and engineering change.
- **Retail & CPG** — store operations, customer operations, merchandising, and the brand-side
  field sales, trade investment and insights workflows. Retail and CPG ship as one portfolio
  rather than two, split by a `retailer` / `cpg` tag: seven retailer-side, three brand-side.

## What a template is

Not a prompt, and not a single skill. A template is a **package** that carries everything a
scenario needs:

| Piece | What it does |
|-------|--------------|
| `skills/<name>/SKILL.md` | The ordered skills the agent runs — Connect → Analyze → Act → Create |
| `skills/<name>/scripts/` | Deterministic Python engines: anything that produces a number, a severity, or a verdict |
| `contracts/*.json` | The versioned JSON contract every skill hands to the next, carrying data + confidence + provenance + citations |
| `references/` | The rules, thresholds and standards excerpts the engines and prompts cite |
| `demo-data/` | Two synthetic scenarios per template — a happy path and a messier one, with expected outputs |

The split matters: **engines compute, the model extracts and drafts.** The model never invents a
severity, a priority or a disposition — it quotes the engine and cites the rule. That is what
makes the output auditable.

Every template is **draft-first**: it prepares work for a person to review and sign off, and it
does not write back to a system of record.

## The gallery

### Manufacturing

| Template | What it does |
|----------|--------------|
| [Quality Inspection & Nonconformance](submissions/manufacturing/quality-inspection) | Clear an inspection lot; draft the NCR |
| [Maintenance Triage](submissions/manufacturing/maintenance-triage) | Rank failure modes; prioritise by criticality |
| [Work Order Assistant](submissions/manufacturing/work-order-assist) | Similar past work + parts readiness in one place |
| [Safety Incident Assist](submissions/manufacturing/safety-incident) | Classify recordability; route with the clocks attached |
| [Supplier Disruption Assist](submissions/manufacturing/supplier-disruption) | Map a shortage through BOM where-used; recommend mitigation |
| [Quality Incident & CAPA](submissions/manufacturing/quality-incident-capa) | NCR → root cause → CAPA → closure readiness |
| [Production Planning](submissions/manufacturing/production-planning) | Capacity, materials, changeover-optimised sequence |
| [Engineering Change & BOM](submissions/manufacturing/engineering-change-bom) | Where-used impact; interface violations; draft the ECN |
| [Supplier Qualification](submissions/manufacturing/supplier-qualification) | Score risk; compare to AVL; draft the memo |
| [Audit Readiness](submissions/manufacturing/audit-readiness) | Clause mapping, evidence gaps, readiness pack |

### Retail & CPG

| Template | Side | What it does |
|----------|------|--------------|
| [Store Associate Assist](submissions/retail-and-cpg/store-associate-assist) | Retailer | The associate's cited answer on the shop floor |
| [Store Task & Promotion Execution](submissions/retail-and-cpg/store-task-promotion-execution) | Retailer | Campaign pack → store-specific readiness plan before launch |
| [Returns & Refund Case](submissions/retail-and-cpg/returns-refund-case) | Retailer | Policy-cited eligibility; fraud signals surfaced, not adjudicated |
| [Product Content & Catalog Enrichment](submissions/retail-and-cpg/product-content-catalog-enrichment) | Retailer | Normalise attributes, score completeness, check regulated claims |
| [Customer Service & Order Support](submissions/retail-and-cpg/customer-service-order-support) | Retailer | Classify intent, assemble context, draft or escalate |
| [Supplier & Vendor Performance Review](submissions/retail-and-cpg/supplier-vendor-performance) | Retailer | OTIF scorecard, issue clusters, corrective action request |
| [Order Intake & O2C Exception](submissions/retail-and-cpg/order-intake-o2c-exception) | Retailer | Validate unstructured orders; route exceptions with corrections |
| [Retail Execution & Perfect Store](submissions/retail-and-cpg/retail-execution-perfect-store) | CPG | Pre-call plan; gaps ranked by revenue, not count |
| [Trade Promotion & Deduction Recovery](submissions/retail-and-cpg/trade-promotion-deduction-recovery) | CPG | Match claims to terms; quantify the disputable amount |
| [Consumer & Market Insight Synthesis](submissions/retail-and-cpg/consumer-market-insight-synthesis) | CPG | Reuse prior research; flag contradictions; check usage rights |

## The skill catalog

Every template's skills are also published, flattened one folder per skill, on a
generated [`catalog`](https://github.com/SravaniSeethi/industry-templates/tree/catalog)
branch:

`https://github.com/SravaniSeethi/industry-templates/tree/catalog`

Any agent platform that adds skills from a public GitHub folder can take the
whole library from that one URL, and the gallery's **Catalog URL** button copies
it. The branch holds only unpacked canonical skills — a root `SKILL.md` plus that
skill's own `scripts/`, `references/`, `contracts/` and `templates/`. Gallery
metadata, human-facing READMEs, demo data and test evidence are excluded.

Each folder is named `<template-slug>-<skill-name>`. The importer's format wants
one flat level, so bare skill names would collide across the gallery — and they
do: `policy-retrieve` belongs to two Retail templates, `knowledge-retrieve` to
one Retail and one Manufacturing template. The prefix keeps every folder unique
and says which template a skill came from.

> These skills are authored for **Cowork** and chain through their package's
> contract. They have not been verified running standalone on another platform,
> so treat the catalog as the skill sources rather than a compatibility promise.

The branch is regenerated from `main` on each deploy. Never edit it by hand.

## Repository layout

```
submissions/<industry>/<slug>/   ← the only folder contributors touch
├── metadata.json            ← catalog details (sidecar, never bundled)
├── README.md                ← the human-facing page content (never bundled)
├── .claude-plugin/plugin.json
├── skills/ contracts/ references/ demo-data/
└── tests/                   ← test report + sample prompts (never bundled)

src/content/templates/       ← GENERATED page frontmatter + body
src/content/guides/          ← GENERATED from each README.md
public/bundles/<slug>.zip    ← GENERATED download package
```

`src/content/` and `public/bundles/` are generated by `scripts/import-submissions.ts`. Never
edit them by hand — edit the submission and re-run the importer. `src/content/` is committed so
that a pull request shows what your submission will publish; `public/bundles/` is not, because a
zip's entry metadata is platform-specific — CI rebuilds it before every deploy.

## Develop locally

```bash
npm install
npm run check:submissions   # validate metadata, write nothing
npm run import:submissions  # regenerate pages + bundles
npm run dev                 # http://localhost:4321/industry-templates
npm run build               # same content validation CI runs
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). One submission folder, one pull request — CI validates
your metadata, generates the page and the download bundle, and deploys on merge.

## Licence and attribution

MIT — see [LICENSE](LICENSE). The site design and submission architecture are adapted from
[`microsoft/cat-agent-skills`](https://github.com/microsoft/cat-agent-skills) (MIT); see
[NOTICE.md](NOTICE.md) for that attribution and for what the demo data and reference excerpts
are (and are not).
