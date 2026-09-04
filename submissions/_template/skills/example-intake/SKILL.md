---
name: example-intake
description: >-
  The AGENT-facing description. This is what the model reads to decide WHEN to
  invoke the skill, so describe the trigger precisely — e.g. "Use when the user
  says 'clear this lot', 'load the results', or when a lot review begins."
  Keep it action-oriented.
---

Write the agent-facing instructions here. The body loads only *after* the agent has decided to
use the skill, so don't restate *when* to use it — that belongs in the frontmatter
`description`. Go straight into how to do the task, in the imperative.

## Instructions

1. Read the inputs listed below and normalise them into `contracts/<your-contract>.v1.json`.
2. Carry `confidence`, `provenance` and `citations` on every field you extract.
3. Hand off to the next skill in the chain.

## Guardrails

- Never invent a value that the deterministic engine is responsible for computing.
- When a document conflicts with measured data, say so and escalate — do not silently pick one.
- Flag low-confidence extractions rather than smoothing them over.

## Tone

Plain and specific. Cite the document and section behind every claim.
