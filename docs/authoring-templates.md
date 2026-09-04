# Authoring an industry template

This is the longer form of [CONTRIBUTING.md](../CONTRIBUTING.md): how the packages in this
gallery are put together, and why they are shaped that way.

## The archetype

Every template in the gallery follows the same span:

```
Connect  →  Analyze  →  Act / Govern  →  Create
```

- **Connect** reads the messy inputs — an email, a PDF excerpt, a CSV export, a form — and
  normalises them into the package's JSON contract.
- **Analyze** runs the deterministic engines: the ranking, the scoring, the tolerance
  comparison, the impact trace.
- **Act / Govern** is the decision step. In some templates it is a routing or mitigation call;
  in the compliance-shaped ones (Audit Readiness, the CAPA closure gate) it is an explicit
  governance check that can *refuse*.
- **Create** drafts the artifact a person will review and sign — an NCR, an ECN, an 8D report, a
  shift plan, a readiness pack.

One skill folder per step, named so that the alphabetical order is not misleading, and each one
reading and writing the shared contract.

## The engine/LLM split

This is the single most important design rule, and the reason these templates hold up in an
audit:

> Anything that produces a **number, a severity, a priority, a disposition or a verdict** is
> computed by a deterministic script. The model extracts, orchestrates across skills, and writes
> the cited prose.

The model never grades a defect or sets a priority from scratch — it quotes the engine's output
and cites the rule the engine applied. Two people running the same lot get the same answer, and
a reviewer can check the engine constant against the numbered section in `references/`.

Practically that means:

- Engine constants **mirror** `references/<rules>.md` section by section, with the section number
  in a comment.
- Engines read JSON and write JSON. No network calls, no model calls, no side effects.
- `demo-data/*/expected/` holds the engine's output for each scenario, committed. That is your
  regression test.

## The contract

Each package carries one versioned contract, e.g. `contracts/mfg.quality-inspection.v1.json`.
Every hop passes not just data but **confidence, provenance and citations**, so escalation is
mechanical: a low-confidence extraction or a document conflict raises itself rather than
relying on the model to remember to mention it.

Version it in the filename. A breaking change is a new `.v2`.

## The two demo scenarios

Every template ships two, and the second one is the point.

- **`scenario-a-happy`** — the clean case. Proves the chain runs end to end.
- **`scenario-b-drama`** — the case where the obvious answer is wrong. A certificate that
  contradicts the measurements. A "minor" change that hits an interface-critical part. A voice
  note that downplays a hospitalisation. A supervisor who wants "operator error, retrain, close
  by Friday".

Scenario B is what a reviewer reads to decide whether to install your template. Write it so that
a naive reviewer, following the obvious path, gets it wrong — and the engine does not.

Ship the **raw** inputs alongside the structured ones (the email, the PDF excerpt, the CSV
export) so the Connect path is genuinely exercised rather than assumed.

## Draft-first, always

No write-back to a system of record. Nothing auto-sent, nothing auto-filed. The template's job is
to prepare the work so a person's review takes minutes instead of hours — and to make the
grounds for every call visible enough that the review is real.

Say the boundary explicitly in your README. "Ends at NCR creation" and "producing the evidence is
human work" are features, not caveats.

## Grounding and copyright

Reference excerpts are **illustrative summaries** of public standards, not the standards
themselves. Cite the clause; do not reproduce the text. Anyone using a template on real work
should hold the standard and replace the excerpts with their own controlled documents.

Demo data is synthetic — invented part numbers, suppliers, people and measurements. Never ship
customer data.
