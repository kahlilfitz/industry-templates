# Maintenance Triage — Cowork Plugin

Helps maintenance technicians move a fault forward. It reads the fault notes, alarm codes and
asset history, identifies the likely failure mode from manuals and past work orders,
prioritizes by asset criticality and downtime impact, and drafts the work-order update with
the recommended action. Starts from documents; historian input is optional. Every
determination cites its grounding and carries confidence + provenance. Ends at the
work-order draft; predictive maintenance (Wave 3) takes it from there.

**Archetype:** Doc Extractor & Summarizer (embeds a rules engine)
**Span:** Connect -> Analyze -> Act · **Trigger:** attended (draft-first)
**For:** maintenance technicians, reliability engineers, shift supervisors, maintenance planners

## Skill chain

| # | Skill | Category | Job | Engine / components |
|---|-------|----------|-----|---------------------|
| 1 | fault-intake | Connect | Read fault notes, alarm/event logs, asset register into the contract | extraction prompt, upload / SharePoint / CMMS |
| 2 | history-retrieve | Connect | Pull prior work orders, similar failures, OEM manual sections | shared retrieval |
| 3 | failure-mode-rank | Analyze | Rank likely failure modes vs symptoms + manual + history | `scripts/fault_rank.py` (deterministic) |
| 4 | criticality-rank | Analyze | Prioritize by asset criticality × downtime cost | `scripts/criticality_score.py` (deterministic) |
| 5 | work-order-update | Act | Draft the WO update + recommended action, cited | `templates/work-order-update-template.md` |

## Contract

Skills chain through the versioned JSON contract `mfg.maintenance-triage.v1`
(`contracts/mfg.maintenance-triage.v1.json`). It carries data + confidence + provenance +
citations on every hop, so escalation is mechanical:

```
{symptoms, asset_id, history} -> {ranked_causes} -> {priority, downtime_cost} -> WO-update.md
```

## Engine/LLM split

Numbers come from the deterministic Python engines. The model does extraction, orchestration
across skills, and drafting the cited work-order prose. The LLM never ranks a cause or sets a
priority from scratch — it quotes the engine output. Rules are encoded as data that cite the
numbered reference sections in `references/`.

## The move that sells it — repeat-failure promotion

A cheap symptomatic fix that keeps coming back is a signal, not a solution. When an overload
reset (or similar) has recurred on an asset **and** a mechanical signal (vibration, bearing
temperature) is emerging, `fault_rank` promotes the underlying root cause over the easy fix
and `criticality_score` escalates the priority. See `demo-data/scenario-b-drama/`.

## Try the demos

```
# Scenario A (happy): clear bearing wear on a class-B pump -> bearing_degradation, P3
python skills/failure-mode-rank/scripts/fault_rank.py \
  --intake demo-data/scenario-a-happy/fault-intake.json --out /tmp/ranked-a.json
python skills/criticality-rank/scripts/criticality_score.py \
  --ranked /tmp/ranked-a.json --out /tmp/triaged-a.json

# Scenario B (drama): looks like a 4th overload reset, but 3 repeats + emerging vibration ->
# bearing_degradation promoted to rank 1, escalated to P1 on a non-redundant class-A asset
python skills/failure-mode-rank/scripts/fault_rank.py \
  --intake demo-data/scenario-b-drama/fault-intake.json --out /tmp/ranked-b.json
python skills/criticality-rank/scripts/criticality_score.py \
  --ranked /tmp/ranked-b.json --out /tmp/triaged-b.json
```

Expected outputs for both scenarios are committed under `demo-data/*/expected/`.

## Boundaries

- Draft-first: the work-order update and recommended action are recommendations pending
  planner / supervisor approval. No CMMS / EAM write-back in v1.
- Historian input is optional — the plugin runs from documents alone.
- **Not predictive maintenance.** This plugin triages the fault in front of you; it does not
  forecast future failures or optimize PM intervals (Wave 3).

## Grounding

OEM equipment manuals, CMMS/EAM work-order history, RCM, and ISO 55000 — see `references/`.
